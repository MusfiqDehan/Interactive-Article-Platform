# 3. A custom `Revision` model, not django-reversion

**Status:** Accepted · **Phase:** 3

## Context

The studio needs revision history with diffs, restore, and autosave
coalescing. `django-reversion` is the obvious library.

## Decision

A custom `Revision` model holding a `snapshot` JSONField, a monotonic
per-article `number`, and the article's `content_hash`.

## Why not django-reversion

Reversion stores an **opaque serialized blob** designed to be replayed into the
Django admin. What the studio needs is the opposite: to *read inside* a
revision.

- **Block-level diffs.** The editor shows which Editor.js blocks were added,
  removed, moved or changed. That requires walking the block array, which means
  the snapshot has to be structured data, not a serialized blob.
- **SEO and placement state in the same snapshot.** A revision that restores
  the body but not the meta description is not a restore.
- **Autosave coalescing.** Editor.js autosaves every few seconds; without
  coalescing, a morning's work is four hundred revisions. `record_edit()`
  merges same-author edits inside a 15-minute window, which needs knowledge of
  what changed — again, structure.

Retrofitting all three onto reversion means storing our own snapshot anyway,
next to its blob.

## Consequences

- `NON_RESTORABLE_FIELDS` exists because a restore must not move an article's
  workflow state or slug. Restoring `status` would publish a draft; restoring
  `slug` would break every live URL.
- `content_hash` in the revision is what makes "no change, no revision" cheap.
- We own the retention question. Nothing prunes revisions yet — a deliberate
  omission, since the table is small and losing history silently is worse than
  a large table.
