"""Building and sending one delivery.

Split from ``tasks.py`` so the interesting parts -- payload shape, idempotency,
what counts as a permanent failure -- are testable without a broker.

**Retryable vs permanent.** A 500 or a timeout means "try again"; a 404 or a
401 means the configuration is wrong and no number of retries will fix it. The
distinction matters because treating everything as retryable spends eight
attempts over thirty hours re-sending to a URL that has a typo in it, and the
operator learns nothing until the log is read a day later.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

import requests
from django.db import transaction
from django.utils import timezone

from common.signing import sign

from .models import ContentDelivery, Destination

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10

#: Statuses where retrying can plausibly succeed. Everything else is a
#: configuration or authorisation problem the receiver is telling us about.
RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def payload_fingerprint(article) -> str:
    """What "unchanged" means for delivery purposes.

    Not ``content_hash`` alone. That covers only the block JSON, because it
    drives the editor's `If-Match` concurrency check and widening it there
    would make unrelated field edits look like content conflicts. But a
    receiver renders the title and excerpt too, so a headline fix with no body
    change has to be re-delivered -- and keying on `content_hash` would decide
    nothing had happened and send nothing, leaving the partner site showing the
    old headline indefinitely.
    """
    material = "|".join(
        [
            article.content_hash,
            article.title,
            article.excerpt,
            article.featured_image,
            str(article.is_live),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_payload(article, destination: Destination, event: str) -> dict:
    """The body sent to a destination.

    Deliberately not the full studio serializer: a receiver needs enough to
    render or invalidate, not our internal workflow state. Sending the whole
    article would also leak draft-side fields to partner sites.
    """
    placement = article.placements.filter(site=destination.target_site).first()
    return {
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "site": {"slug": article.site.slug, "name": article.site.name},
        "article": {
            "id": article.pk,
            "slug": article.slug,
            "title": article.title,
            "excerpt": article.excerpt,
            "locale": article.locale,
            "content_hash": article.content_hash,
            "published_at": article.published_at.isoformat()
            if article.published_at
            else None,
            "updated_at": article.updated_at.isoformat(),
            "is_live": article.is_live,
            "canonical_url": placement.resolved_canonical() if placement else "",
            "path_slug": placement.path_slug if placement else article.slug,
        },
    }


def enqueue(article, event: str = "publish") -> list[ContentDelivery]:
    """Create the delivery rows for an article's event, skipping duplicates.

    Returns only the rows that are actually new. Re-publishing unchanged
    content produces an idempotency key that already exists, so
    ``get_or_create`` hands back the delivered row and nothing is sent -- which
    is the point, and why the return value is filtered rather than complete.
    """
    destinations = Destination.objects.filter(
        site=article.site, is_active=True, disabled_at__isnull=True
    )
    created = []
    for destination in destinations:
        if not destination.accepts(event):
            continue
        delivery, is_new = ContentDelivery.objects.get_or_create(
            idempotency_key=ContentDelivery.key_for(
                destination.pk, article.pk, event, payload_fingerprint(article)
            ),
            defaults={
                "destination": destination,
                "article": article,
                "article_label": article.title[:300],
                "event": event,
                "event_id": uuid.uuid4().hex,
                "next_attempt_at": timezone.now(),
                "payload_snapshot": build_payload(article, destination, event),
            },
        )
        if is_new:
            created.append(delivery)
    return created


def send(delivery: ContentDelivery) -> bool:
    """Attempt one delivery. Returns True on success.

    Never raises for a failed send: the outcome is recorded on the row and the
    retry is scheduled there. A task that raised would be retried by Celery on
    *its* schedule as well as ours, and the two would compound.
    """
    destination = delivery.destination
    url = destination.resolved_url()
    if not url:
        delivery.state = "skipped"
        delivery.last_error = "Destination has no endpoint URL."
        delivery.save(update_fields=["state", "last_error", "updated_at"])
        return False

    body = json.dumps(delivery.payload_snapshot, separators=(",", ":"))
    signature, timestamp = sign(destination.secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-CMS-Signature": signature,
        "X-CMS-Timestamp": timestamp,
        # Lets the receiver dedupe independently of us -- our retries and its
        # own at-least-once handling are different problems.
        "X-CMS-Event-Id": delivery.event_id,
        "X-CMS-Event": delivery.event,
        **(destination.headers or {}),
    }

    ContentDelivery.objects.filter(pk=delivery.pk).update(state="delivering")

    try:
        response = requests.post(url, data=body, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        destination.record_failure(str(exc))
        delivery.schedule_retry(f"{type(exc).__name__}: {exc}")
        return False

    if 200 <= response.status_code < 300:
        destination.record_success()
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        delivery.mark_delivered(response.status_code, payload)
        return True

    destination.record_failure(f"HTTP {response.status_code}")
    delivery.response_status = response.status_code
    if response.status_code in RETRYABLE_STATUSES:
        delivery.schedule_retry(f"HTTP {response.status_code}: {response.text[:500]}")
    else:
        # Permanent: stop immediately rather than burning the remaining seven
        # attempts on a URL or credential that is simply wrong.
        delivery.state = "abandoned"
        delivery.attempts += 1
        delivery.next_attempt_at = None
        delivery.last_error = (
            f"HTTP {response.status_code} (not retryable): {response.text[:500]}"
        )
        delivery.save(
            update_fields=[
                "state", "attempts", "next_attempt_at", "last_error",
                "response_status", "updated_at",
            ]
        )
    return False


def fan_out(article, event: str = "publish") -> int:
    """Enqueue and dispatch an article's deliveries. Returns how many were new."""
    from .tasks import deliver_content

    deliveries = enqueue(article, event)
    ids = [delivery.pk for delivery in deliveries]
    if ids:
        # on_commit, because a task that starts before this transaction lands
        # would look up a delivery row that does not exist yet.
        transaction.on_commit(
            lambda: [deliver_content.delay(delivery_id) for delivery_id in ids]
        )
    return len(ids)
