"""Snapshotting, diffing and restoring article revisions.

The diff is **block-level**, keyed on Editor.js block ids, because that is what
an editor actually wants to see: "you changed paragraph 3 and moved the table",
not a 4000-character text diff of a JSON blob. This is the concrete reason the
serializer backfills a stable ``id`` onto every block -- if ids churned between
saves every block would read as removed-and-re-added and the diff would be
worthless.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max

#: Fields captured verbatim in a snapshot. Deliberately explicit: a
#: ``__dict__`` sweep would silently start capturing (and restoring) internal
#: columns like ``views_count`` the moment someone adds one.
SNAPSHOT_FIELDS = (
    "title",
    "slug",
    "excerpt",
    "content",
    "featured_image",
    "status",
    "is_featured",
    "locale",
    "meta_title",
    "meta_description",
    "focus_keyword",
    "canonical_url",
)

#: Restoring must not resurrect a past publication state. Restoring a snapshot
#: taken while published would otherwise republish the article as a side effect
#: of viewing history.
NON_RESTORABLE_FIELDS = frozenset({"status", "slug"})


def snapshot_of(article) -> dict:
    """Capture the restorable state of an article."""
    data = {}
    for name in SNAPSHOT_FIELDS:
        if hasattr(article, name):
            data[name] = getattr(article, name)
    data["category_id"] = article.category_id
    return data


def create_revision(article, user=None, reason: str = "", is_autosave: bool = False):
    """Append a revision, allocating the next number safely.

    The number is allocated while holding a row lock on the article. A plain
    ``MAX(number) + 1`` read outside a lock lets two concurrent saves compute
    the same value; one then fails the unique constraint, which for an autosave
    surfaces as a spurious 500 on a keystroke.
    """
    from apps.articles.models import Article

    from .models import Revision

    with transaction.atomic():
        # Serialises revision creation for this article and nothing else.
        Article.unscoped.select_for_update().get(pk=article.pk)
        last = Revision.unscoped.filter(article=article).aggregate(Max("number"))
        number = (last["number__max"] or 0) + 1

        return Revision.objects.create(
            site=article.site,
            article=article,
            number=number,
            snapshot=snapshot_of(article),
            content_hash=article.content_hash,
            status=article.status,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            reason=reason,
            is_autosave=is_autosave,
        )


#: An autosave by the same author inside this window updates the previous
#: revision instead of appending one. Editor.js autosaves on a 2-second debounce,
#: so appending unconditionally would produce hundreds of near-identical rows per
#: session and make the history panel unusable -- the thing it exists to serve.
AUTOSAVE_COALESCE_SECONDS = 15 * 60


def record_edit(article, user=None, reason: str = "edited"):
    """Snapshot an edit, coalescing rapid autosaves by the same author.

    Returns the revision, or None when the content is unchanged -- saving a
    title-only tweak should not manufacture a content revision.
    """
    from django.utils import timezone

    from .models import Revision

    latest = Revision.unscoped.filter(article=article).order_by("-number").first()
    if latest is not None and latest.content_hash == article.content_hash:
        return None

    if (
        latest is not None
        and latest.is_autosave
        and latest.created_by_id == getattr(user, "pk", None)
        and (timezone.now() - latest.created_at).total_seconds()
        < AUTOSAVE_COALESCE_SECONDS
    ):
        latest.snapshot = snapshot_of(article)
        latest.content_hash = article.content_hash
        latest.status = article.status
        latest.reason = reason
        latest.save(update_fields=["snapshot", "content_hash", "status", "reason"])
        return latest

    return create_revision(article, user=user, reason=reason, is_autosave=True)


def _blocks(snapshot: dict) -> list[dict]:
    content = snapshot.get("content") or {}
    if isinstance(content, dict):
        blocks = content.get("blocks") or []
        return [b for b in blocks if isinstance(b, dict)]
    return []


def _index(blocks: list[dict]) -> dict[str, dict]:
    """Map block id -> block, skipping blocks with no id.

    Positional fallback is deliberately *not* used: matching an id-less block by
    index would report a spurious "changed" for every block after an insertion.
    """
    return {b["id"]: b for b in blocks if b.get("id")}


def diff_snapshots(old: dict, new: dict) -> dict:
    """Structured diff between two snapshots."""
    fields = {}
    for name in SNAPSHOT_FIELDS:
        if name == "content":
            continue
        before, after = old.get(name), new.get(name)
        if before != after:
            fields[name] = {"before": before, "after": after}

    old_blocks, new_blocks = _blocks(old), _blocks(new)
    old_by_id, new_by_id = _index(old_blocks), _index(new_blocks)
    old_order = [b["id"] for b in old_blocks if b.get("id")]
    new_order = [b["id"] for b in new_blocks if b.get("id")]

    added = [bid for bid in new_order if bid not in old_by_id]
    removed = [bid for bid in old_order if bid not in new_by_id]
    changed = [
        bid
        for bid in new_order
        if bid in old_by_id and old_by_id[bid].get("data") != new_by_id[bid].get("data")
    ]

    # "Moved" compares position among blocks that exist in *both* versions.
    # Comparing raw indices would flag every block after an insertion as moved,
    # which is technically true and completely useless to read.
    surviving_old = [bid for bid in old_order if bid in new_by_id]
    surviving_new = [bid for bid in new_order if bid in old_by_id]
    moved = (
        [bid for i, bid in enumerate(surviving_new) if surviving_old[i] != bid]
        if len(surviving_old) == len(surviving_new)
        else []
    )

    return {
        "fields": fields,
        "blocks": {
            "added": added,
            "removed": removed,
            "changed": changed,
            "moved": moved,
        },
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "moved": len(moved),
            "before": len(old_blocks),
            "after": len(new_blocks),
        },
    }


def restore(article, revision, user=None):
    """Restore an article's content from a revision.

    Non-destructive in two senses: the current state is snapshotted first, and
    ``status``/``slug`` are not restored. Rolling the status back would silently
    unpublish (or republish) an article as a side effect of a content restore,
    and rolling the slug back would break every link that the redirect created
    when it changed.
    """
    from .transitions import record

    create_revision(article, user=user, reason="pre-restore snapshot")

    snapshot = revision.snapshot or {}
    applied = []
    for name, value in snapshot.items():
        if name in NON_RESTORABLE_FIELDS:
            continue
        field = name
        if not hasattr(article, field):
            continue
        setattr(article, field, value)
        applied.append(field)

    article.save()
    record(
        site=article.site,
        action="revision_restore",
        user=user,
        article=article,
        metadata={"revision": revision.number, "fields": sorted(applied)},
    )
    return create_revision(
        article, user=user, reason=f"restored from v{revision.number}"
    )
