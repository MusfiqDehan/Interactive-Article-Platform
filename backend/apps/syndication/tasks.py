"""Delivery tasks.

Two entry points: ``deliver_content`` sends one row, and ``retry_due_deliveries``
is a beat sweep that picks up rows whose backoff has elapsed. The sweep is what
makes delivery survive a worker restart -- an in-flight task that dies leaves
its row in ``delivering``, and without the sweep nothing would ever look at it
again.

The tasks themselves are thin: everything interesting lives in ``delivery.py``,
where it can be tested without a broker.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from common.locks import advisory_lock

from .delivery import send
from .models import ContentDelivery

logger = logging.getLogger(__name__)

#: How long a row may sit in `delivering` before the sweep assumes the worker
#: holding it died. Comfortably longer than the HTTP timeout plus overhead.
STUCK_AFTER_SECONDS = 300
BATCH_SIZE = 50


@shared_task(name="syndication.deliver_content", bind=True, max_retries=0)
def deliver_content(self, delivery_id: int) -> dict:
    """Send one delivery.

    ``max_retries=0`` on purpose: retries are ours, scheduled on the row with
    the backoff in `common.retry`. Letting Celery retry as well would give two
    independent schedules racing on the same row, and the receiver would see
    duplicate POSTs at unpredictable intervals.
    """
    delivery = (
        ContentDelivery.objects.select_related("destination", "article")
        .filter(pk=delivery_id)
        .first()
    )
    if delivery is None:
        return {"delivery": delivery_id, "skipped": "gone"}
    if delivery.state == "delivered":
        # Celery acks late, so a task whose worker died after the POST but
        # before the ack is re-run. The row already says it succeeded.
        return {"delivery": delivery_id, "skipped": "already delivered"}
    if not delivery.destination.is_deliverable:
        delivery.state = "skipped"
        delivery.last_error = "Destination is disabled."
        delivery.save(update_fields=["state", "last_error", "updated_at"])
        return {"delivery": delivery_id, "skipped": "destination disabled"}

    ok = send(delivery)
    return {"delivery": delivery_id, "delivered": ok, "attempts": delivery.attempts}


@shared_task(name="syndication.retry_due_deliveries")
def retry_due_deliveries() -> dict:
    """Re-dispatch failed deliveries whose backoff has elapsed."""
    with advisory_lock("syndication:retry-sweep", timeout=120) as acquired:
        if acquired is False:
            return {"skipped": "another worker holds the sweep lock"}

        now = timezone.now()
        # Rows stuck in `delivering` are reclaimed: the only way to reach that
        # state and stay there is a worker dying mid-request, and without this
        # they would be invisible to every subsequent sweep.
        stuck = ContentDelivery.objects.filter(
            state="delivering",
            updated_at__lt=now - timezone.timedelta(seconds=STUCK_AFTER_SECONDS),
        )
        reclaimed = stuck.update(state="failed", next_attempt_at=now)

        due = list(
            ContentDelivery.objects.filter(
                state__in=("pending", "failed"), next_attempt_at__lte=now
            )
            .order_by("next_attempt_at")
            .values_list("pk", flat=True)[:BATCH_SIZE]
        )
        for delivery_id in due:
            transaction.on_commit(
                lambda pk=delivery_id: deliver_content.delay(pk)
            )
        return {"reclaimed": reclaimed, "dispatched": len(due)}
