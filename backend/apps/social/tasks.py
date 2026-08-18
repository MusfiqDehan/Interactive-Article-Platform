"""Social dispatch.

``publish_target`` publishes one platform's copy. It is per-target, not
per-post, because that is the only shape in which "the image was too big for X"
can leave LinkedIn, Facebook and Threads published — which is what the editor
needs and what a post-level state cannot express.

``dispatch_due_posts`` is the beat sweep that honours ``scheduled_at``. Our
scheduling, not the provider's: a direct integration has no scheduling API, so
using the aggregator's would make the semantics change on the day we swap.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from common.locks import advisory_lock
from common.retry import MAX_ATTEMPTS, backoff_seconds

from .models import SocialAccount, SocialPost, SocialPostTarget
from .providers import (
    ProviderAuthError,
    ProviderError,
    ProviderNotReady,
    get_provider,
)

logger = logging.getLogger(__name__)


def idempotency_key(target: SocialPostTarget) -> str:
    """Stable across retries of the same target, unique across targets.

    Includes the caption so that editing and re-sending is a genuinely new
    post, while a redelivered task for an unchanged target is not.
    """
    import hashlib

    raw = f"{target.post_id}:{target.account_id}:{target.platform}:{target.caption}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


@shared_task(name="social.publish_target", bind=True, max_retries=0)
def publish_target(self, target_id: int) -> dict:
    """Publish one target. Retries are scheduled on the row, not by Celery."""
    target = (
        SocialPostTarget.objects.select_related("account", "post", "post__site")
        .filter(pk=target_id)
        .first()
    )
    if target is None:
        return {"target": target_id, "skipped": "gone"}
    if target.state in ("published", "cancelled"):
        # acks_late means this task can arrive twice; the row already answers.
        return {"target": target_id, "skipped": target.state}

    account = target.account
    if not account.is_usable:
        target.mark_failed(
            f"The {account.platform} account needs reconnecting ({account.status})."
        )
        target.post.recompute_state()
        return {"target": target_id, "failed": "account unusable"}

    provider = get_provider(account)

    problems = provider.validate(
        platform=target.platform, caption=target.caption, media=target.media
    )
    if problems:
        # Validation failures are permanent by definition -- the same payload
        # will fail identically forever. Fail this target only.
        target.mark_failed(" ".join(problems))
        target.post.recompute_state()
        return {"target": target_id, "failed": "validation", "problems": problems}

    SocialPostTarget.objects.filter(pk=target.pk).update(state="publishing")

    try:
        media = provider.upload_media(platform=target.platform, media=target.media)
        result = provider.publish(
            platform=target.platform,
            caption=target.caption,
            media=media,
            idempotency_key=idempotency_key(target),
            state=target.request_snapshot or {},
        )
    except ProviderNotReady as exc:
        # Not a failure: the platform is still working. The attempt counter
        # deliberately does not advance, and the provider's state is stored so
        # the retry resumes rather than starting a second container.
        snapshot = {**(target.request_snapshot or {}), **(exc.state or {})}
        target.state = "retrying"
        target.request_snapshot = snapshot
        target.next_attempt_at = timezone.now() + timezone.timedelta(
            seconds=exc.retry_after
        )
        target.last_error = str(exc)
        target.save(
            update_fields=[
                "state", "request_snapshot", "next_attempt_at", "last_error",
                "updated_at",
            ]
        )
        target.post.recompute_state()
        return {"target": target_id, "not_ready": exc.retry_after}
    except ProviderAuthError as exc:
        account.mark_expired(str(exc))
        target.mark_failed(str(exc))
        target.post.recompute_state()
        return {"target": target_id, "failed": "auth"}
    except ProviderError as exc:
        target.attempts += 1
        if exc.permanent or target.attempts >= MAX_ATTEMPTS:
            target.mark_failed(str(exc))
        else:
            target.state = "retrying"
            target.last_error = str(exc)[:2000]
            target.next_attempt_at = timezone.now() + timezone.timedelta(
                seconds=backoff_seconds(target.attempts + 1)
            )
            target.save(
                update_fields=[
                    "state", "attempts", "last_error", "next_attempt_at", "updated_at",
                ]
            )
        target.post.recompute_state()
        return {"target": target_id, "failed": str(exc), "attempts": target.attempts}

    target.attempts += 1
    target.mark_published(result.external_id, result.url, result.raw)
    SocialAccount.objects.filter(pk=account.pk).update(last_used_at=timezone.now())
    target.post.recompute_state()
    return {"target": target_id, "published": result.external_id}


@shared_task(name="social.dispatch_due_posts")
def dispatch_due_posts() -> dict:
    """Publish posts whose scheduled time has arrived, and retry due targets."""
    with advisory_lock("social:dispatch", timeout=120) as acquired:
        if acquired is False:
            return {"skipped": "another worker holds the dispatch lock"}

        now = timezone.now()
        dispatched = 0

        due_posts = SocialPost.objects.filter(
            state="scheduled", scheduled_at__lte=now
        ).only("id")
        for post in due_posts:
            # Re-asserting `state="scheduled"` in the UPDATE is the guarantee:
            # a second worker's update matches zero rows and it moves on, so a
            # post cannot be dispatched twice.
            claimed = SocialPost.objects.filter(pk=post.pk, state="scheduled").update(
                state="publishing"
            )
            if not claimed:
                continue
            target_ids = list(
                SocialPostTarget.objects.filter(post_id=post.pk, state="pending")
                .values_list("pk", flat=True)
            )
            for target_id in target_ids:
                transaction.on_commit(lambda pk=target_id: publish_target.delay(pk))
            dispatched += len(target_ids)

        retry_ids = list(
            SocialPostTarget.objects.filter(
                state="retrying", next_attempt_at__lte=now
            ).values_list("pk", flat=True)[:100]
        )
        for target_id in retry_ids:
            transaction.on_commit(lambda pk=target_id: publish_target.delay(pk))

        return {"dispatched": dispatched, "retried": len(retry_ids)}


@shared_task(name="social.refresh_metrics")
def refresh_metrics(max_targets: int = 100) -> dict:
    """Pull engagement numbers for recently published targets.

    Only recent ones: a post's metrics stop moving after a few days, and
    re-fetching the whole archive every hour would spend the platform's rate
    limit on numbers that have not changed.
    """
    cutoff = timezone.now() - timezone.timedelta(days=7)
    targets = (
        SocialPostTarget.objects.filter(state="published", published_at__gte=cutoff)
        .exclude(external_id="")
        .select_related("account")
        .order_by("metrics_fetched_at")[:max_targets]
    )

    updated = 0
    for target in targets:
        provider = get_provider(target.account)
        if not provider.capabilities().can_fetch_metrics:
            continue
        try:
            metrics = provider.fetch_metrics(external_id=target.external_id)
        except Exception:
            # Metrics are decoration. A platform being down must never mark a
            # successfully published post as anything other than published.
            logger.warning("Metrics fetch failed for target %s", target.pk, exc_info=True)
            continue
        target.metrics = metrics
        target.metrics_fetched_at = timezone.now()
        target.save(update_fields=["metrics", "metrics_fetched_at", "updated_at"])
        updated += 1

    return {"updated": updated}
