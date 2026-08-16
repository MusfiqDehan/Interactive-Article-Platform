"""Event ingestion: validate, buffer, return.

The ingest endpoint is on the hot path of every page view, so it **never
writes to the database**. It validates, pushes onto a Redis list, and returns
202. A beat task drains the list in batches into one ``bulk_create``.

That indirection is the whole design. A direct insert per event turns a page
view into a database write, puts the busiest table in the schema on the
critical path of the site's own rendering, and makes an analytics spike look
identical to a database outage. Buffering decouples them: the drain can fall
behind, and readers never notice.

The buffer is deliberately allowed to lose events. Redis is configured
without persistence for this key, and a lost batch costs an approximate
number in a dashboard -- which is the right trade against blocking a reader.
"""

from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.utils import timezone

from .models import EVENT_NAMES

logger = logging.getLogger(__name__)

BUFFER_KEY = "analytics:events"
#: Bounded so a runaway client cannot exhaust Redis. Beyond this the oldest
#: events are dropped, which is the correct sacrifice: a dashboard number goes
#: slightly stale, rather than the cache every page depends on falling over.
MAX_BUFFER = 100_000
#: Per drain. Big enough that one INSERT is worth the round trip, small enough
#: that a batch cannot hold a transaction open for long.
DRAIN_BATCH = 5_000


def _redis():
    """The raw Redis client, or None if unavailable.

    django-redis is configured with IGNORE_EXCEPTIONS, so a failure here is a
    None rather than an exception -- and the caller degrades to dropping the
    event, never to a 500 on a page view.
    """
    try:
        return cache.client.get_client(write=True)
    except Exception:  # pragma: no cover - depends on the cache backend
        return None


def validate(payload: dict) -> dict | None:
    """Normalise one event, or return None if it is not usable.

    Rejects rather than raises: this runs on a beacon whose sender cannot see
    the response and would not act on it anyway. A malformed event is dropped
    and counted, not turned into an error page.
    """
    name = str(payload.get("name") or "")
    if name not in EVENT_NAMES:
        return None
    return {
        "name": name,
        "article_id": payload.get("article_id") or None,
        "target_id": str(payload.get("target_id") or "")[:100],
        "path": str(payload.get("path") or "")[:500],
        "referrer": str(payload.get("referrer") or "")[:500],
        "locale": str(payload.get("locale") or "")[:10],
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


def buffer(site_id: int, session: str, events: list[dict]) -> int:
    """Push validated events onto the buffer. Returns how many were accepted."""
    client = _redis()
    if client is None:
        return 0

    now = timezone.now().isoformat()
    payloads = [
        json.dumps({**event, "site_id": site_id, "session": session, "occurred_at": now})
        for event in events
    ]
    if not payloads:
        return 0

    try:
        pipeline = client.pipeline()
        pipeline.rpush(BUFFER_KEY, *payloads)
        # Trim to the newest MAX_BUFFER in the same round trip, so a burst
        # cannot grow the list unboundedly between drains.
        pipeline.ltrim(BUFFER_KEY, -MAX_BUFFER, -1)
        pipeline.execute()
    except Exception:
        logger.warning("Could not buffer %s analytics events", len(payloads), exc_info=True)
        return 0
    return len(payloads)


def drain(limit: int = DRAIN_BATCH) -> list[dict]:
    """Pop up to ``limit`` events off the buffer.

    ``LPOP count`` is atomic, so two drains running concurrently cannot take
    the same events -- which matters because the beat schedule and a manual
    run can overlap.
    """
    client = _redis()
    if client is None:
        return []
    try:
        raw = client.lpop(BUFFER_KEY, limit)
    except Exception:
        logger.warning("Could not drain the analytics buffer", exc_info=True)
        return []
    if not raw:
        return []
    if isinstance(raw, (bytes, str)):
        raw = [raw]

    events = []
    for item in raw:
        try:
            events.append(json.loads(item))
        except (TypeError, ValueError):
            continue
    return events


def buffered_count() -> int:
    client = _redis()
    if client is None:
        return 0
    try:
        return int(client.llen(BUFFER_KEY))
    except Exception:
        return 0
