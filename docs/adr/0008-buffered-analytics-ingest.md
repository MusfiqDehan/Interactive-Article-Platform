# 8. Buffer analytics in Redis, never write on the read path

**Status:** Accepted · **Phase:** 7

## Context

`Article.views_count` was incremented by an unauthenticated, unthrottled
endpoint on every article read. That is a database write on the hottest read
path, and trivially inflatable with curl.

## Decision

The ingest endpoint validates, `RPUSH`es onto a bounded Redis list, and returns
**202 without touching the database**. A beat task drains batches into one
`bulk_create`. Rollups are recomputed, not incremented.

## Why the indirection

A direct insert per event makes an analytics spike indistinguishable from a
database outage, because they are the same event: the busiest table in the
schema sitting on the critical path of the site's own rendering. Buffering
decouples them — the drain can fall behind and readers never notice.

The buffer is deliberately **allowed to lose events**. It is capped at 100k and
trimmed on write. Losing a batch costs an approximate number in a dashboard;
blocking a reader costs the reader.

## Why recompute rather than increment

The drain can write an event after its day has already been rolled up. An
incremental counter has no way to notice; re-aggregating a two-day window is
one grouped query and is always correct.

## Privacy

A session is `sha256(ip + user-agent + daily salt)`. The salt rotates daily, so
the same visitor hashes differently tomorrow. "Unique visitors today" is
answerable and cross-day tracking of an individual is impossible **by
construction**, not by policy — there is no configuration that turns it on.

## Consequences

- `Article.views_count` survives, because every existing ordering reads it. It
  is now a cache of the event log, resynced by the rollup, rather than a
  counter written on the read path.
- The beacon carries its API key in the query string. `sendBeacon` cannot set
  headers, and using `fetch` instead loses exactly the end-of-session events
  worth having. The middleware accepts a query key on that **one path only**,
  and the key is write-events-scoped — deliberately not the read key, which can
  see unpublished articles.
- Raw events expire after ~400 days; rollups are permanent, so year-on-year
  comparisons survive the retention window.
