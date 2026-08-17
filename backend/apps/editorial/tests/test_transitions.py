"""State machine: legality, role guards, side effects and the audit trail."""

import pytest
from django.utils import timezone

from apps.editorial.models import AuditLogEntry
from apps.editorial.transitions import (
    TransitionError,
    TransitionPermissionDenied,
    available,
    effective_site_role,
    legal_targets,
    perform,
)

pytestmark = pytest.mark.django_db


class TestLegality:
    def test_publish_from_draft(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site)
        assert article.status == "published"
        assert article.is_live is True

    def test_cannot_approve_a_draft(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        with pytest.raises(TransitionError, match="Cannot approve"):
            perform(article, "approve", user=admin, site=default_site)

    def test_unknown_transition_is_rejected(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        with pytest.raises(TransitionError, match="Unknown transition"):
            perform(article, "teleport", user=admin, site=default_site)

    def test_full_happy_path(self, article_factory, admin, author, default_site,
                             membership_factory):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)

        perform(article, "submit", user=author, site=default_site)
        assert article.status == "in_review"
        perform(article, "approve", user=admin, site=default_site)
        assert article.status == "approved"
        perform(article, "publish", user=admin, site=default_site)
        assert article.status == "published"
        perform(article, "archive", user=admin, site=default_site)
        assert article.status == "archived"
        assert article.is_live is False

    def test_legal_targets(self):
        assert legal_targets("archived") == {"published", "draft"}


class TestVisibilityIsDerived:
    """is_live must never disagree with status, whatever route was taken."""

    @pytest.mark.parametrize(
        "transition,expected_live",
        [
            ("publish", True),
            ("archive", False),
        ],
    )
    def test_is_live_follows_status(
        self, article_factory, admin, default_site, transition, expected_live
    ):
        article = article_factory(status="draft")
        if transition == "archive":
            perform(article, "publish", user=admin, site=default_site)
        perform(article, transition, user=admin, site=default_site)
        article.refresh_from_db()
        assert article.is_live is expected_live

    def test_narrow_save_still_persists_derived_columns(
        self, article_factory, admin, default_site
    ):
        """Regression guard for the update_fields trap.

        A transition saves only the columns it touched. If Article.save() did
        not union in the fields it derives, the row would say published while
        is_live stayed False -- visible in the studio, invisible to the public,
        and with no error anywhere.
        """
        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site)

        from apps.articles.models import Article

        fresh = Article.unscoped.get(pk=article.pk)
        assert fresh.status == "published"
        assert fresh.is_live is True
        assert fresh.published_at is not None
        assert fresh.last_published_at is not None


class TestRoleGuards:
    def test_author_may_submit_own_article(
        self, article_factory, author, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        perform(article, "submit", user=author, site=default_site)
        assert article.status == "in_review"

    def test_author_may_not_submit_someone_elses(
        self, article_factory, author, user_factory, default_site, membership_factory
    ):
        other = user_factory(role="author")
        membership_factory(other, default_site, role="author")
        article = article_factory(status="draft", author=author)
        with pytest.raises(TransitionPermissionDenied, match="their own"):
            perform(article, "submit", user=other, site=default_site)

    def test_author_may_not_publish(
        self, article_factory, author, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        with pytest.raises(TransitionPermissionDenied, match="editor"):
            perform(article, "publish", user=author, site=default_site)

    def test_editor_may_publish_anyones(
        self, article_factory, author, user_factory, default_site, membership_factory
    ):
        editor = user_factory(role="author")
        membership_factory(editor, default_site, role="editor")
        article = article_factory(status="draft", author=author)
        perform(article, "publish", user=editor, site=default_site)
        assert article.status == "published"

    def test_non_member_is_denied(self, article_factory, user_factory, default_site):
        stranger = user_factory(role="author")
        article = article_factory(status="draft")
        with pytest.raises(TransitionPermissionDenied, match="access to this site"):
            perform(article, "publish", user=stranger, site=default_site)

    def test_global_admin_is_owner_everywhere(self, admin, default_site, other_site):
        assert effective_site_role(admin, default_site) == "owner"
        assert effective_site_role(admin, other_site) == "owner"

    def test_anonymous_has_no_role(self, default_site):
        from django.contrib.auth.models import AnonymousUser

        assert effective_site_role(AnonymousUser(), default_site) is None
        assert effective_site_role(None, default_site) is None


class TestAvailableTransitions:
    def test_author_sees_submit_not_publish(
        self, article_factory, author, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        names = {t["name"] for t in available(article, author, site=default_site)}
        assert "submit" in names
        assert "publish" not in names

    def test_editor_sees_publish(
        self, article_factory, user_factory, default_site, membership_factory
    ):
        editor = user_factory(role="author")
        membership_factory(editor, default_site, role="editor")
        article = article_factory(status="draft")
        names = {t["name"] for t in available(article, editor, site=default_site)}
        assert {"publish", "schedule", "archive"} <= names

    def test_schedule_is_offered_before_a_date_is_picked(
        self, article_factory, admin, default_site
    ):
        """The menu must offer Schedule so the user can *choose* a date.

        `available()` answers "may this person do this", not "would it succeed
        with no arguments" -- running the argument guard here would hide the
        action at exactly the moment it is needed.
        """
        article = article_factory(status="draft")
        names = {t["name"] for t in available(article, admin, site=default_site)}
        assert "schedule" in names

        # ...and attempting it without a date still fails loudly.
        with pytest.raises(TransitionError):
            perform(article, "schedule", user=admin, site=default_site)


class TestScheduleGuard:
    def test_requires_a_time(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        with pytest.raises(TransitionError, match="scheduled publish time is required"):
            perform(article, "schedule", user=admin, site=default_site)

    def test_rejects_a_past_time(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        past = timezone.now() - timezone.timedelta(minutes=5)
        with pytest.raises(TransitionError, match="must be in the future"):
            perform(
                article, "schedule", user=admin, site=default_site,
                scheduled_publish_at=past,
            )

    def test_accepts_a_future_time(self, article_factory, admin, default_site):
        article = article_factory(status="draft")
        when = timezone.now() + timezone.timedelta(hours=1)
        perform(
            article, "schedule", user=admin, site=default_site,
            scheduled_publish_at=when,
        )
        assert article.status == "scheduled"
        assert article.scheduled_publish_at == when


class TestPublicationTimestamps:
    def test_published_at_is_stamped_once_and_never_rewritten(
        self, article_factory, admin, default_site
    ):
        """datePublished must not move when an article is republished.

        Rewriting it would tell search engines that a two-year-old article was
        written today, every time somebody fixed a typo and republished.
        """
        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site)
        first = article.published_at

        perform(article, "unpublish", user=admin, site=default_site)
        perform(article, "publish", user=admin, site=default_site)
        article.refresh_from_db()

        assert article.published_at == first
        assert article.last_published_at > first

    def test_publishing_clears_the_schedule(
        self, article_factory, admin, default_site
    ):
        """Otherwise the sweep would keep finding the article due forever."""
        article = article_factory(status="draft")
        perform(
            article, "schedule", user=admin, site=default_site,
            scheduled_publish_at=timezone.now() + timezone.timedelta(hours=1),
        )
        perform(article, "publish", user=admin, site=default_site)
        article.refresh_from_db()
        assert article.scheduled_publish_at is None


class TestAuditTrail:
    def test_every_transition_is_recorded(
        self, article_factory, admin, default_site
    ):
        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site, reason="launch")

        entry = AuditLogEntry.objects.get(article=article, action="transition")
        assert entry.from_state == "draft"
        assert entry.to_state == "published"
        assert entry.actor == admin
        assert entry.actor_label == admin.email
        assert entry.metadata["transition"] == "publish"
        assert entry.metadata["reason"] == "launch"
        assert entry.site_id == default_site.pk

    def test_system_transitions_are_labelled_system(
        self, article_factory, default_site
    ):
        article = article_factory(status="draft")
        perform(article, "publish", user=None, system=True)
        entry = AuditLogEntry.objects.get(article=article)
        assert entry.actor is None
        assert entry.actor_label == "system"

    def test_a_failed_transition_writes_no_entry(
        self, article_factory, author, default_site, membership_factory
    ):
        """The state change and its record commit together or not at all."""
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        with pytest.raises(TransitionPermissionDenied):
            perform(article, "publish", user=author, site=default_site)

        assert AuditLogEntry.objects.filter(article=article).count() == 0
        article.refresh_from_db()
        assert article.status == "draft"

    def test_system_bypass_still_enforces_state_legality(
        self, article_factory, default_site
    ):
        """system=True skips roles only -- an illegal transition still fails."""
        article = article_factory(status="draft")
        with pytest.raises(TransitionError):
            perform(article, "approve", user=None, system=True)
