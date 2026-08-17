"""Scheduled publishing, including the exactly-once property under concurrency."""

import threading

import pytest
from django.db import connections
from django.utils import timezone

from apps.articles.models import Article
from apps.editorial.models import AuditLogEntry
from apps.editorial.tasks import _sweep, publish_due_articles, unpublish_due_articles

pytestmark = pytest.mark.django_db


def _due(article_factory, minutes_ago=1, **kwargs):
    """An article whose scheduled time has already passed."""
    article = article_factory(status="draft", **kwargs)
    article.status = "scheduled"
    article.scheduled_publish_at = timezone.now() - timezone.timedelta(
        minutes=minutes_ago
    )
    article.save()
    return article


class TestSweep:
    def test_publishes_a_due_article(self, article_factory):
        article = _due(article_factory)
        result = _sweep(
            transition="publish", status="scheduled", field="scheduled_publish_at"
        )

        article.refresh_from_db()
        assert article.status == "published"
        assert article.is_live is True
        assert article.pk in result["processed"]

    def test_ignores_articles_not_yet_due(self, article_factory):
        article = article_factory(status="draft")
        article.status = "scheduled"
        article.scheduled_publish_at = timezone.now() + timezone.timedelta(hours=2)
        article.save()

        _sweep(transition="publish", status="scheduled", field="scheduled_publish_at")
        article.refresh_from_db()
        assert article.status == "scheduled"

    def test_ignores_articles_in_the_wrong_state(self, article_factory):
        """A due time on a draft is stale data, not an instruction to publish."""
        article = article_factory(status="draft")
        article.scheduled_publish_at = timezone.now() - timezone.timedelta(minutes=5)
        article.save()

        _sweep(transition="publish", status="scheduled", field="scheduled_publish_at")
        article.refresh_from_db()
        assert article.status == "draft"

    def test_records_a_system_audit_entry(self, article_factory):
        article = _due(article_factory)
        _sweep(transition="publish", status="scheduled", field="scheduled_publish_at")

        entry = AuditLogEntry.objects.get(article=article, action="transition")
        assert entry.actor_label == "system"
        assert entry.metadata["reason"] == "scheduled"
        assert entry.metadata["source"] == "beat"

    def test_one_bad_article_does_not_abort_the_batch(
        self, article_factory, monkeypatch
    ):
        good = _due(article_factory)
        bad = _due(article_factory)

        real_perform = __import__(
            "apps.editorial.tasks", fromlist=["perform"]
        ).perform

        def exploding(article, *args, **kwargs):
            if article.pk == bad.pk:
                raise RuntimeError("boom")
            return real_perform(article, *args, **kwargs)

        monkeypatch.setattr("apps.editorial.tasks.perform", exploding)

        result = _sweep(
            transition="publish", status="scheduled", field="scheduled_publish_at"
        )

        good.refresh_from_db()
        bad.refresh_from_db()
        assert good.status == "published"
        assert bad.status == "scheduled"
        assert bad.pk in result["failed"]

    def test_unpublish_sweep_archives_and_clears(self, article_factory, admin,
                                                 default_site):
        from apps.editorial.transitions import perform

        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site)
        article.scheduled_unpublish_at = timezone.now() - timezone.timedelta(minutes=1)
        article.save()

        _sweep(
            transition="archive",
            status="published",
            field="scheduled_unpublish_at",
            clear_field=True,
        )
        article.refresh_from_db()
        assert article.status == "archived"
        assert article.is_live is False
        assert article.scheduled_unpublish_at is None


@pytest.mark.django_db(transaction=True)
class TestExactlyOnce:
    """The load-bearing guarantee: N workers, one publish.

    ``transaction=True`` is required -- the guarantee depends on real commits
    and row locks, and pytest-django's default wraps each test in a transaction
    that would never let a second connection observe the first's work.

    Note that these tests *truncate every table* on teardown, taking rows
    created by data migrations with them. Nothing in the suite may depend on
    migration-seeded data; the ``_ensure_default_site`` autouse fixture in
    conftest exists to make that safe.
    """

    def test_three_concurrent_sweeps_publish_once(self, article_factory):
        article = _due(article_factory)

        barrier = threading.Barrier(3)
        errors = []

        def worker():
            try:
                # Maximise overlap: all three hit the claim query together.
                barrier.wait(timeout=10)
                _sweep(
                    transition="publish",
                    status="scheduled",
                    field="scheduled_publish_at",
                )
            except Exception as exc:  # pragma: no cover - surfaces real races
                errors.append(exc)
            finally:
                # Each thread gets its own connection; leaking them wedges the
                # test database on teardown.
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert not errors, errors

        article.refresh_from_db()
        assert article.status == "published"

        # The real assertion. A double publish leaves two transition entries,
        # two revisions, and (in production) two social posts.
        entries = AuditLogEntry.objects.filter(
            article=article, action="transition", to_state="published"
        )
        assert entries.count() == 1, (
            f"expected exactly one publish, got {entries.count()}"
        )

    def test_concurrent_sweeps_over_many_articles_publish_each_once(
        self, article_factory
    ):
        articles = [_due(article_factory) for _ in range(8)]
        barrier = threading.Barrier(3)

        def worker():
            try:
                barrier.wait(timeout=10)
                _sweep(
                    transition="publish",
                    status="scheduled",
                    field="scheduled_publish_at",
                )
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        for article in articles:
            article.refresh_from_db()
            assert article.status == "published"
            assert (
                AuditLogEntry.objects.filter(
                    article=article, action="transition", to_state="published"
                ).count()
                == 1
            )


class TestTaskEntrypoints:
    def test_publish_task_takes_the_lock(self, article_factory):
        article = _due(article_factory)
        result = publish_due_articles()
        article.refresh_from_db()
        assert article.status == "published"
        assert article.pk in result["processed"]

    def test_second_caller_skips_while_the_lock_is_held(self, article_factory):
        """The advisory lock prevents redundant sweeps, not double publishes."""
        from django.core.cache import cache

        cache.set("lock:editorial:publish-due", "someone-else", 60)
        try:
            result = publish_due_articles()
        finally:
            cache.delete("lock:editorial:publish-due")
        assert "skipped" in result

    def test_sweep_proceeds_when_the_cache_is_unavailable(
        self, article_factory, monkeypatch
    ):
        """A Redis outage must not silently stop scheduled publishing.

        With IGNORE_EXCEPTIONS the cache returns None rather than raising, and
        an advisory lock that treats None as "held" would quietly freeze every
        schedule for the duration of the outage.
        """
        article = _due(article_factory)
        monkeypatch.setattr("common.locks.cache.add", lambda *a, **kw: None)
        monkeypatch.setattr("common.locks.cache.get", lambda *a, **kw: None)

        publish_due_articles()
        article.refresh_from_db()
        assert article.status == "published"

    def test_unpublish_entrypoint(self, article_factory, admin, default_site):
        from apps.editorial.transitions import perform

        article = article_factory(status="draft")
        perform(article, "publish", user=admin, site=default_site)
        article.scheduled_unpublish_at = timezone.now() - timezone.timedelta(minutes=1)
        article.save()

        unpublish_due_articles()
        article.refresh_from_db()
        assert article.status == "archived"


class TestCrossTenantSweep:
    def test_sweeps_every_site(self, article_factory, default_site, other_site,
                               user_factory):
        """The beat task serves all tenants; it has no request to scope to."""
        author = user_factory(role="author")
        a = _due(article_factory)
        b = article_factory(status="draft", site=other_site, author=author)
        b.status = "scheduled"
        b.scheduled_publish_at = timezone.now() - timezone.timedelta(minutes=1)
        b.save()

        _sweep(transition="publish", status="scheduled", field="scheduled_publish_at")

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.status == "published"
        assert b.status == "published"
        assert AuditLogEntry.objects.get(article=b).site_id == other_site.pk
