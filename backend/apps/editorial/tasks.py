"""Background work for the editorial workflow.

The scheduling sweep is the piece with a real correctness requirement: an
article scheduled for a given minute must go live **exactly once**, with any
number of workers running. Three things combine to give that, in order of
importance:

1. The claim query filters on ``status=SCHEDULED`` *and* takes
   ``FOR UPDATE SKIP LOCKED``. A second worker either skips the locked row or,
   once the first commits, no longer matches the filter -- because publishing
   moves the article out of the scheduled state. **This is the guarantee.**
2. Each article is claimed and published in its own transaction, so one bad
   article cannot roll back an entire batch.
3. An advisory Redis lock stops every worker running the same sweep on the same
   tick. It is an efficiency measure and is explicitly allowed to fail open;
   see ``common.locks``.

Side effects that leave the database (cache busting, frontend revalidation) are
fired from ``transaction.on_commit``. Firing them inline would announce a
publish that a later rollback un-does.
"""

from __future__ import annotations

import json
import logging

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.cache import bump_content_version
from common.locks import advisory_lock
from common.signing import sign

from .states import PUBLISHED, SCHEDULED
from .transitions import TransitionError, perform

logger = logging.getLogger(__name__)

#: Bounded so a backlog cannot turn one tick into a multi-minute transaction.
#: Leftovers are picked up by the next tick 60 seconds later.
SWEEP_BATCH_SIZE = 200


@shared_task(name="editorial.publish_due_articles")
def publish_due_articles():
    """Publish every article whose scheduled time has arrived."""
    with advisory_lock("editorial:publish-due", timeout=120) as acquired:
        if not acquired:
            return {"skipped": "another worker holds the sweep lock"}
        return _sweep(
            transition="publish",
            status=SCHEDULED,
            field="scheduled_publish_at",
        )


@shared_task(name="editorial.unpublish_due_articles")
def unpublish_due_articles():
    """Take down every article whose scheduled unpublish time has arrived."""
    with advisory_lock("editorial:unpublish-due", timeout=120) as acquired:
        if not acquired:
            return {"skipped": "another worker holds the sweep lock"}
        return _sweep(
            transition="archive",
            status=PUBLISHED,
            field="scheduled_unpublish_at",
            clear_field=True,
        )


def _sweep(*, transition: str, status: str, field: str, clear_field: bool = False):
    from apps.articles.models import Article

    now = timezone.now()
    processed, failed = [], []

    # Read candidate ids outside the per-article transactions. Holding one long
    # transaction over the whole batch would keep locks for its full duration
    # and block editors saving unrelated articles.
    candidates = list(
        Article.unscoped.filter(**{"status": status, f"{field}__lte": now})
        .order_by(field, "id")
        .values_list("pk", flat=True)[:SWEEP_BATCH_SIZE]
    )

    for pk in candidates:
        try:
            article_id = _claim_and_transition(pk, transition, status, field, now, clear_field)
        except TransitionError as exc:
            # Legitimate: the article changed state between the scan and the
            # claim. Not an error condition, but worth seeing in the log.
            logger.info("Skipped scheduled %s for article %s: %s", transition, pk, exc)
            continue
        except Exception:
            logger.exception("Scheduled %s failed for article %s", transition, pk)
            failed.append(pk)
            continue
        if article_id is not None:
            processed.append(article_id)

    return {"processed": processed, "failed": failed, "scanned": len(candidates)}


def _claim_and_transition(pk, transition, status, field, now, clear_field):
    """Claim one article and transition it, or return None if already taken."""
    from apps.articles.models import Article

    with transaction.atomic():
        article = (
            Article.unscoped.select_for_update(skip_locked=True)
            # Re-asserting status and the due time is what makes this
            # exactly-once: after a competing worker commits, this filter no
            # longer matches and we get None rather than a second publish.
            .filter(**{"pk": pk, "status": status, f"{field}__lte": now})
            .first()
        )
        if article is None:
            return None

        if clear_field:
            setattr(article, field, None)

        perform(
            article,
            transition,
            user=None,
            system=True,
            reason="scheduled",
            metadata={"scheduled_for": now.isoformat(), "source": "beat"},
        )
        if clear_field:
            article.save(update_fields=[field])

        _schedule_post_publish(article)
        return article.pk


def _schedule_post_publish(article):
    """Queue the post-transition fan-out, after this transaction commits."""
    article_id = article.pk
    transaction.on_commit(lambda: after_publish.delay(article_id))


@shared_task(name="editorial.after_publish")
def after_publish(article_id: int):
    """The publish chain: snapshot, invalidate, revalidate, fan out.

    Split from the transition itself so that a failing webhook or an unreachable
    frontend retries on its own without ever rolling back the publish. Each step
    is independently safe to re-run, because ``acks_late`` means this task can
    be delivered more than once.
    """
    from apps.articles.models import Article

    from .revisions import create_revision

    article = Article.unscoped.filter(pk=article_id).select_related("site").first()
    if article is None:
        return {"missing": article_id}

    results = {}

    try:
        create_revision(article, user=None, reason="published")
        results["revision"] = "ok"
    except Exception:
        logger.exception("Revision snapshot failed for article %s", article_id)
        results["revision"] = "failed"

    bump_content_version(article.site_id)
    results["cache"] = "bumped"

    revalidate_site.delay(
        article.site_id,
        paths=["/", "/articles", f"/articles/{article.slug}"],
        tags=["articles", f"article:{article.slug}", "sitemap"],
    )
    results["revalidate"] = "queued"

    try:
        from apps.syndication.delivery import fan_out

        # Idempotent by construction: the delivery key hashes the article's
        # content_hash, so re-running this task after a redelivered Celery
        # message enqueues nothing new. That property is what lets the whole
        # chain be safe under `acks_late`.
        results["deliveries"] = fan_out(article, event="publish")
    except Exception:
        # A destination misconfiguration must not fail the publish chain --
        # the article is already live, and the delivery sweep will pick up
        # anything that was enqueued.
        logger.exception("Delivery fan-out failed for article %s", article_id)
        results["deliveries"] = "failed"

    # Phase 6 attaches social here; Phase 7 search indexing.
    return results


@shared_task(
    name="editorial.revalidate_site",
    bind=True,
    max_retries=5,
    default_retry_delay=30,
)
def revalidate_site(self, site_id: int, paths=None, tags=None):
    """Ask a site's Next.js deployment to purge specific paths and tags.

    Signed with the shared HMAC scheme (``common.signing``) so the endpoint can
    be exposed without authentication headers that would need rotating.
    """
    from apps.tenancy.models import Site, SiteSettings

    site = Site.objects.filter(pk=site_id).first()
    if site is None:
        return {"skipped": "unknown site"}

    site_settings = SiteSettings.objects.filter(site=site).first()
    url = (getattr(site_settings, "revalidate_url", "") or "").strip()
    secret = (getattr(site_settings, "revalidate_secret", "") or "").strip()

    # Fall back to process-level config for single-site deployments, where
    # per-site rows are unnecessary ceremony.
    url = url or getattr(settings, "FRONTEND_REVALIDATE_URL", "")
    secret = secret or getattr(settings, "CMS_REVALIDATE_SECRET", "")

    if not url or not secret:
        # Not an error: a site may legitimately have no ISR frontend attached.
        return {"skipped": "revalidation not configured for this site"}

    body = json.dumps({"paths": paths or [], "tags": tags or []}, separators=(",", ":"))
    signature, timestamp = sign(secret, body)

    try:
        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-CMS-Signature": signature,
                "X-CMS-Timestamp": timestamp,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise self.retry(exc=exc)

    if response.status_code >= 500:
        # 4xx is not retried: a bad signature or malformed body will fail the
        # same way forever, and retrying only delays the log line that explains
        # it. 5xx is a frontend that may simply be restarting.
        raise self.retry(exc=RuntimeError(f"revalidate returned {response.status_code}"))

    return {"status": response.status_code, "url": url, "paths": paths, "tags": tags}
