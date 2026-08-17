"""Revision capture, block-level diffing, and restore."""

import pytest

from apps.editorial.models import Revision
from apps.editorial.revisions import (
    create_revision,
    diff_snapshots,
    record_edit,
    restore,
    snapshot_of,
)

pytestmark = pytest.mark.django_db


def blocks(*items):
    return {"blocks": list(items)}


def block(bid, text):
    return {"id": bid, "type": "paragraph", "data": {"text": text}}


class TestSnapshot:
    def test_captures_restorable_fields_only(self, article_factory):
        article = article_factory(title="Snap", content=blocks(block("a", "one")))
        snapshot = snapshot_of(article)
        assert snapshot["title"] == "Snap"
        assert snapshot["content"]["blocks"][0]["id"] == "a"
        # Counters are not content and must never be rolled back by a restore.
        assert "views_count" not in snapshot

    def test_numbers_are_monotonic(self, article_factory, admin):
        article = article_factory()
        a = create_revision(article, user=admin)
        b = create_revision(article, user=admin)
        assert (a.number, b.number) == (1, 2)

    def test_revision_inherits_the_articles_site(self, article_factory, default_site):
        article = article_factory()
        revision = create_revision(article)
        assert revision.site_id == default_site.pk


class TestRecordEdit:
    def test_unchanged_content_creates_nothing(self, article_factory, admin):
        article = article_factory(content=blocks(block("a", "one")))
        assert record_edit(article, user=admin) is not None
        assert record_edit(article, user=admin) is None
        assert Revision.objects.filter(article=article).count() == 1

    def test_rapid_autosaves_by_one_author_coalesce(self, article_factory, admin):
        """Editor.js autosaves every couple of seconds; appending each one
        would bury the history panel in near-identical rows."""
        article = article_factory(content=blocks(block("a", "one")))
        record_edit(article, user=admin)

        article.content = blocks(block("a", "two"))
        article.save()
        record_edit(article, user=admin)

        article.content = blocks(block("a", "three"))
        article.save()
        record_edit(article, user=admin)

        revisions = Revision.objects.filter(article=article)
        assert revisions.count() == 1
        assert revisions.first().snapshot["content"]["blocks"][0]["data"]["text"] == "three"

    def test_a_different_author_starts_a_new_revision(
        self, article_factory, admin, user_factory
    ):
        """Coalescing across authors would attribute one person's edit to
        another in the history."""
        other = user_factory(role="author")
        article = article_factory(content=blocks(block("a", "one")))
        record_edit(article, user=admin)

        article.content = blocks(block("a", "two"))
        article.save()
        record_edit(article, user=other)

        assert Revision.objects.filter(article=article).count() == 2


class TestDiff:
    def test_detects_added_removed_and_changed(self):
        old = {"content": blocks(block("a", "one"), block("b", "two"))}
        new = {"content": blocks(block("a", "one"), block("c", "three"))}
        diff = diff_snapshots(old, new)
        assert diff["blocks"]["added"] == ["c"]
        assert diff["blocks"]["removed"] == ["b"]
        assert diff["blocks"]["changed"] == []

    def test_detects_edited_text(self):
        old = {"content": blocks(block("a", "one"))}
        new = {"content": blocks(block("a", "ONE"))}
        assert diff_snapshots(old, new)["blocks"]["changed"] == ["a"]

    def test_insertion_does_not_report_everything_as_moved(self):
        """The naive index comparison marks every block after an insert as
        moved, which is true and useless."""
        old = {"content": blocks(block("a", "1"), block("b", "2"), block("c", "3"))}
        new = {
            "content": blocks(
                block("a", "1"), block("x", "new"), block("b", "2"), block("c", "3")
            )
        }
        diff = diff_snapshots(old, new)
        assert diff["blocks"]["added"] == ["x"]
        assert diff["blocks"]["moved"] == []

    def test_detects_a_genuine_reorder(self):
        old = {"content": blocks(block("a", "1"), block("b", "2"))}
        new = {"content": blocks(block("b", "2"), block("a", "1"))}
        assert diff_snapshots(old, new)["blocks"]["moved"]

    def test_reports_scalar_field_changes(self):
        old = {"title": "Before", "content": blocks()}
        new = {"title": "After", "content": blocks()}
        diff = diff_snapshots(old, new)
        assert diff["fields"]["title"] == {"before": "Before", "after": "After"}

    def test_blocks_without_ids_are_ignored_rather_than_mismatched(self):
        old = {"content": {"blocks": [{"type": "paragraph", "data": {"text": "x"}}]}}
        new = {"content": {"blocks": [{"type": "paragraph", "data": {"text": "y"}}]}}
        diff = diff_snapshots(old, new)
        assert diff["blocks"] == {
            "added": [],
            "removed": [],
            "changed": [],
            "moved": [],
        }
        # Still counted, so the UI can say "1 block -> 1 block".
        assert diff["counts"]["before"] == 1


class TestRestore:
    def test_restores_content(self, article_factory, admin, default_site):
        article = article_factory(content=blocks(block("a", "original")))
        revision = create_revision(article, user=admin)

        article.content = blocks(block("a", "ruined"))
        article.save()

        restore(article, revision, user=admin)
        article.refresh_from_db()
        assert article.content["blocks"][0]["data"]["text"] == "original"

    def test_restore_does_not_change_publication_state(
        self, article_factory, admin, default_site
    ):
        """Restoring old content must not silently unpublish the article.

        The snapshot was taken while the article was a draft; rolling `status`
        back with it would take a live page down as a side effect of an
        editorial undo.
        """
        from apps.editorial.transitions import perform

        article = article_factory(status="draft", content=blocks(block("a", "v1")))
        draft_revision = create_revision(article, user=admin)

        perform(article, "publish", user=admin, site=default_site)
        article.content = blocks(block("a", "v2"))
        article.save()

        restore(article, draft_revision, user=admin)
        article.refresh_from_db()

        assert article.content["blocks"][0]["data"]["text"] == "v1"
        assert article.status == "published"
        assert article.is_live is True

    def test_restore_does_not_change_the_slug(self, article_factory, admin):
        """Rolling the slug back would break every link the rename redirected."""
        article = article_factory(title="Original Title")
        revision = create_revision(article, user=admin)
        original_slug = article.slug

        article.slug = "renamed-on-purpose"
        article.save()

        restore(article, revision, user=admin)
        article.refresh_from_db()
        assert article.slug == "renamed-on-purpose"
        assert article.slug != original_slug

    def test_restore_snapshots_the_pre_restore_state(self, article_factory, admin):
        """An undo must itself be undoable."""
        article = article_factory(content=blocks(block("a", "v1")))
        revision = create_revision(article, user=admin)
        article.content = blocks(block("a", "v2"))
        article.save()

        before = Revision.objects.filter(article=article).count()
        restore(article, revision, user=admin)
        after = Revision.objects.filter(article=article).count()
        assert after > before

    def test_restore_is_audited(self, article_factory, admin):
        from apps.editorial.models import AuditLogEntry

        article = article_factory(content=blocks(block("a", "v1")))
        revision = create_revision(article, user=admin)
        restore(article, revision, user=admin)

        entry = AuditLogEntry.objects.get(article=article, action="revision_restore")
        assert entry.metadata["revision"] == revision.number
