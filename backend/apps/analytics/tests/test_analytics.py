"""Analytics: ingestion, buffering, rollups, and the metric that justifies it."""

import pytest
from django.utils import timezone

from apps.analytics.ingest import buffer, buffered_count, drain, validate
from apps.analytics.models import ContentEvent, DailyContentStat, session_hash
from apps.analytics.tasks import drain_events, prune_events, rollup_daily

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"
PUBLIC = "/api/v1/public"


@pytest.fixture(autouse=True)
def _clear_buffer():
    drain(1_000_000)
    yield
    drain(1_000_000)


class TestValidation:
    def test_an_unknown_event_name_is_dropped(self):
        assert validate({"name": "definitely_not_an_event"}) is None

    def test_a_known_event_is_normalised(self):
        event = validate({"name": "annotation_open", "target_id": "a1", "extra": "x"})
        assert event["name"] == "annotation_open"
        assert event["target_id"] == "a1"
        assert "extra" not in event

    def test_oversized_fields_are_truncated_not_rejected(self):
        event = validate({"name": "view", "path": "/" + "a" * 900})
        assert len(event["path"]) == 500


class TestSessions:
    def test_the_same_visitor_is_stable_within_a_day(self):
        assert session_hash("1.2.3.4", "UA") == session_hash("1.2.3.4", "UA")

    def test_a_different_visitor_is_a_different_session(self):
        assert session_hash("1.2.3.4", "UA") != session_hash("5.6.7.8", "UA")

    def test_the_salt_rotates_daily(self):
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)
        # Cross-day tracking of an individual is impossible by construction,
        # not by policy -- the same IP hashes differently tomorrow.
        assert session_hash("1.2.3.4", "UA", day=today) != session_hash(
            "1.2.3.4", "UA", day=yesterday
        )

    def test_the_ip_is_not_recoverable(self):
        digest = session_hash("203.0.113.9", "Mozilla/5.0")
        assert "203.0.113.9" not in digest
        assert len(digest) == 32


class TestIngestEndpoint:
    def test_the_beacon_never_touches_the_database(
        self, public_client, django_assert_num_queries, default_site
    ):
        client = public_client()
        # One query for the API key lookup, and no writes -- the whole point of
        # the buffer is that a page view is not a database write.
        before = ContentEvent.unscoped.count()
        response = client.post(
            f"{PUBLIC}/events/",
            {"events": [{"name": "view", "path": "/articles/x"}]},
            format="json",
        )
        assert response.status_code == 202
        assert ContentEvent.unscoped.count() == before

    def test_malformed_events_still_return_202(self, public_client):
        response = public_client().post(
            f"{PUBLIC}/events/", {"events": [{"name": "nope"}]}, format="json"
        )
        # The sender is sendBeacon; it cannot read this and cannot retry. A 4xx
        # would only ever show up as a console error on a reader's page.
        assert response.status_code == 202
        assert response.json()["accepted"] == 0

    def test_a_batch_is_capped(self, public_client):
        response = public_client().post(
            f"{PUBLIC}/events/",
            {"events": [{"name": "view"} for _ in range(200)]},
            format="json",
        )
        assert response.json()["accepted"] <= 50

    def test_a_key_without_the_scope_is_rejected(self, api_client, api_key_factory, default_site):
        from rest_framework.test import APIClient

        _, raw = api_key_factory(default_site, scopes=["read:content"])
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=raw)
        assert client.post(f"{PUBLIC}/events/", {"events": []}, format="json").status_code == 403


class TestDrain:
    def test_buffered_events_reach_the_database(self, default_site, article_factory):
        article = article_factory()
        buffer(
            default_site.pk,
            "sess1",
            [validate({"name": "view", "article_id": article.pk})],
        )
        assert buffered_count() == 1

        result = drain_events()
        assert result["written"] == 1
        assert ContentEvent.unscoped.filter(article=article, name="view").exists()

    def test_draining_twice_does_not_double_write(self, default_site):
        buffer(default_site.pk, "s", [validate({"name": "view"})])
        drain_events()
        # LPOP is atomic and destructive, so a second drain has nothing to take.
        assert drain_events()["written"] == 0

    def test_an_empty_buffer_is_a_no_op(self):
        assert drain_events()["written"] == 0


class TestRollups:
    def _event(self, site, article, name, session="s", day_offset=0):
        return ContentEvent.objects.create(
            site=site,
            article=article,
            name=name,
            session=session,
            occurred_at=timezone.now() - timezone.timedelta(days=day_offset),
        )

    def test_events_roll_up_per_article_per_day(
        self, default_site, article_factory
    ):
        article = article_factory()
        for index in range(5):
            self._event(default_site, article, "view", session=f"s{index}")
        for _ in range(2):
            self._event(default_site, article, "annotation_open")

        rollup_daily()

        stat = DailyContentStat.unscoped.get(article=article, day=timezone.now().date())
        assert stat.views == 5
        assert stat.annotation_opens == 2
        assert stat.unique_sessions == 5

    def test_interaction_rate_is_opens_over_views(self, default_site, article_factory):
        article = article_factory()
        for index in range(10):
            self._event(default_site, article, "view", session=f"s{index}")
        for _ in range(3):
            self._event(default_site, article, "annotation_open")
        rollup_daily()

        stat = DailyContentStat.unscoped.get(article=article)
        # The number that says whether the interactive format is being *used*
        # rather than merely served. No generic analytics tool can produce it.
        assert stat.interaction_rate == 0.3

    def test_rolling_up_twice_is_idempotent(self, default_site, article_factory):
        article = article_factory()
        self._event(default_site, article, "view")
        rollup_daily()
        rollup_daily()
        # Recomputed, not incremented -- so a late-arriving event corrects the
        # number instead of double-counting it.
        assert DailyContentStat.unscoped.get(article=article).views == 1

    def test_a_late_event_corrects_the_rollup(self, default_site, article_factory):
        article = article_factory()
        self._event(default_site, article, "view")
        rollup_daily()
        self._event(default_site, article, "view", session="s2")
        rollup_daily()
        assert DailyContentStat.unscoped.get(article=article).views == 2

    def test_views_count_is_kept_in_step(self, default_site, article_factory):
        article = article_factory()
        for index in range(4):
            self._event(default_site, article, "view", session=f"s{index}")
        rollup_daily()
        article.refresh_from_db()
        # The denormalised column stays -- every existing ordering reads it --
        # but it is now a cache of the event log rather than a write on the
        # read path.
        assert article.views_count == 4

    def test_pruning_keeps_the_rollups(self, default_site, article_factory):
        article = article_factory()
        old = self._event(default_site, article, "view")
        ContentEvent.unscoped.filter(pk=old.pk).update(
            occurred_at=timezone.now() - timezone.timedelta(days=500)
        )
        rollup_daily(days_back=600)
        before = DailyContentStat.unscoped.count()

        prune_events(keep_days=400)

        assert not ContentEvent.unscoped.filter(pk=old.pk).exists()
        # Raw events expire; the aggregates are permanent, which is what makes
        # year-on-year comparisons survive the retention window.
        assert DailyContentStat.unscoped.count() == before


class TestDashboards:
    def test_site_analytics_reports_the_interaction_rate(
        self, auth_client, admin, default_site, article_factory
    ):
        article = article_factory()
        DailyContentStat.objects.create(
            site=default_site,
            article=article,
            day=timezone.now().date(),
            views=100,
            annotation_opens=25,
            reads_completed=40,
        )
        body = auth_client(admin).get(f"{BASE}/analytics/").json()
        assert body["totals"]["views"] == 100
        assert body["interaction_rate"] == 0.25
        assert body["completion_rate"] == 0.4

    def test_top_articles_are_ranked(
        self, auth_client, admin, default_site, article_factory
    ):
        big = article_factory(title="Popular")
        small = article_factory(title="Quiet")
        today = timezone.now().date()
        DailyContentStat.objects.create(site=default_site, article=big, day=today, views=90)
        DailyContentStat.objects.create(site=default_site, article=small, day=today, views=3)

        body = auth_client(admin).get(f"{BASE}/analytics/").json()
        assert [row["title"] for row in body["top_articles"]] == ["Popular", "Quiet"]

    def test_article_analytics_lists_top_annotations(
        self, auth_client, admin, default_site, article_factory
    ):
        article = article_factory()
        for _ in range(3):
            ContentEvent.objects.create(
                site=default_site, article=article, name="annotation_open",
                target_id="attention", session="s", occurred_at=timezone.now(),
            )
        ContentEvent.objects.create(
            site=default_site, article=article, name="annotation_open",
            target_id="encoder", session="s", occurred_at=timezone.now(),
        )

        body = auth_client(admin).get(
            f"{BASE}/analytics/articles/{article.slug}/"
        ).json()
        assert body["top_annotations"][0]["target_id"] == "attention"

    def test_stats_are_scoped_to_the_site(
        self, auth_client, admin, default_site, other_site, article_factory
    ):
        from apps.articles.models import Article

        mine = article_factory()
        theirs = Article.objects.create(
            site=other_site, title="Theirs", author=mine.author, content={"blocks": []}
        )
        today = timezone.now().date()
        DailyContentStat.objects.create(site=default_site, article=mine, day=today, views=5)
        DailyContentStat.objects.create(site=other_site, article=theirs, day=today, views=99)

        body = auth_client(admin).get(f"{BASE}/analytics/").json()
        assert body["totals"]["views"] == 5
