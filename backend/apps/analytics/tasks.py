"""Draining the event buffer and rolling it up."""

from __future__ import annotations

import logging
from collections import defaultdict

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from common.locks import advisory_lock

from .ingest import DRAIN_BATCH, buffered_count, drain
from .models import ContentEvent, DailyContentStat

logger = logging.getLogger(__name__)

#: Event name -> the DailyContentStat column it feeds.
ROLLUP_COLUMNS = {
    "view": "views",
    "read_complete": "reads_completed",
    "annotation_open": "annotation_opens",
    "hotspot_open": "hotspot_opens",
    "media_play": "media_plays",
    "outbound_click": "outbound_clicks",
    "share": "shares",
}


@shared_task(name="analytics.drain_events")
def drain_events(limit: int = DRAIN_BATCH) -> dict:
    """Move buffered events into the database in one bulk insert."""
    with advisory_lock("analytics:drain", timeout=120) as acquired:
        if acquired is False:
            return {"skipped": "another worker is draining"}

        events = drain(limit)
        if not events:
            return {"written": 0, "remaining": buffered_count()}

        rows = []
        for event in events:
            occurred = parse_datetime(event.get("occurred_at") or "") or timezone.now()
            if timezone.is_naive(occurred):
                occurred = timezone.make_aware(occurred)
            rows.append(
                ContentEvent(
                    site_id=event["site_id"],
                    name=event["name"],
                    article_id=event.get("article_id") or None,
                    target_id=event.get("target_id", ""),
                    path=event.get("path", ""),
                    referrer=event.get("referrer", ""),
                    locale=event.get("locale", ""),
                    session=event.get("session", ""),
                    metadata=event.get("metadata") or {},
                    occurred_at=occurred,
                )
            )

        # ignore_conflicts: an article deleted between the beacon and the drain
        # leaves a dangling FK, and losing one event is better than losing the
        # whole batch to it.
        ContentEvent.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)
        return {"written": len(rows), "remaining": buffered_count()}


@shared_task(name="analytics.rollup_daily")
def rollup_daily(days_back: int = 1) -> dict:
    """Recompute ``DailyContentStat`` for the recent past.

    Recomputed rather than incremented. Incrementing is faster and wrong: the
    drain can write an event after its day has already been rolled up, and an
    incremental counter has no way to notice. Re-aggregating a two-day window
    costs one grouped query and is always correct.
    """
    today = timezone.now().date()
    start = today - timezone.timedelta(days=days_back)

    grouped = (
        ContentEvent.unscoped.filter(occurred_at__date__gte=start)
        .values("site_id", "article_id", "occurred_at__date")
        .annotate(
            **{
                column: Count("id", filter=Q(name=name))
                for name, column in ROLLUP_COLUMNS.items()
            },
            unique_sessions=Count("session", distinct=True, filter=Q(name="view")),
        )
    )

    written = 0
    for row in grouped:
        DailyContentStat.unscoped.update_or_create(
            site_id=row["site_id"],
            article_id=row["article_id"],
            day=row["occurred_at__date"],
            defaults={
                column: row[column] for column in [*ROLLUP_COLUMNS.values(), "unique_sessions"]
            },
        )
        written += 1

    synced = _sync_view_counts(start)
    return {"rows": written, "articles_synced": synced}


def _sync_view_counts(since) -> int:
    """Keep ``Article.views_count`` in step with the rollups.

    The denormalised column stays because every existing response and ordering
    reads it; it is now a cache of the event log rather than a counter written
    on the read path. Summing all-time from the rollups keeps the two from
    drifting apart, which an increment-on-view could never guarantee.

    Scoped to articles that *have* rollup rows, so it can only correct a count
    upward or sideways -- never reset one to zero. That is safe because
    ``prune_events`` deletes raw events and never the aggregates, so an
    article's rows are permanent once written. Deleting rollups by hand is the
    one case this will not notice.
    """
    from apps.articles.models import Article

    totals = (
        DailyContentStat.unscoped.filter(article__isnull=False)
        .values("article_id")
        .annotate(total=Count("id"))
    )
    article_ids = [row["article_id"] for row in totals]
    if not article_ids:
        return 0

    from django.db.models import Sum

    sums = dict(
        DailyContentStat.unscoped.filter(article_id__in=article_ids)
        .values_list("article_id")
        .annotate(total=Sum("views"))
    )
    updated = []
    for article in Article.unscoped.filter(pk__in=sums).only("id", "views_count"):
        total = sums.get(article.pk, 0) or 0
        if article.views_count != total:
            article.views_count = total
            updated.append(article)
    if updated:
        # bulk_update, not save(): Article.save() recomputes plain_text,
        # word_count and content_hash, which is a lot of work to do per article
        # for a counter that touches none of them.
        Article.unscoped.bulk_update(updated, ["views_count"], batch_size=500)
    return len(updated)


@shared_task(name="analytics.prune_events")
def prune_events(keep_days: int = 400) -> dict:
    """Drop raw events past the retention window.

    The rollups are permanent; the raw log is not. Keeping a little over a
    year means year-on-year comparisons still work from rollups while the
    append-only table stays a size a single database can serve.
    """
    cutoff = timezone.now() - timezone.timedelta(days=keep_days)
    deleted, _ = ContentEvent.unscoped.filter(occurred_at__lt=cutoff).delete()
    return {"deleted": deleted}
