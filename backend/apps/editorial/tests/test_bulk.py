"""Bulk transitions -- where partial failure is the normal case."""

import pytest

BASE = "/api/v1/studio"
URL = f"{BASE}/articles/bulk-transition/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(user_factory, default_site, membership_factory):
    user = user_factory(role="author")
    membership_factory(user, default_site, role="editor")
    return user


@pytest.fixture
def writer(user_factory, default_site, membership_factory):
    user = user_factory(role="author")
    membership_factory(user, default_site, role="author")
    return user


class TestBulkTransition:
    def test_publishes_many(self, auth_client, editor, article_factory):
        articles = [article_factory(status="draft") for _ in range(3)]
        response = auth_client(editor).post(
            URL,
            {"slugs": [a.slug for a in articles], "transition": "publish"},
            format="json",
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["requested"], body["succeeded"], body["failed"]) == (3, 3, 0)
        for article in articles:
            article.refresh_from_db()
            assert article.status == "published"

    def test_one_bad_article_does_not_block_the_rest(
        self, auth_client, editor, article_factory
    ):
        """The whole point of the endpoint.

        Rolling back the batch would punish the valid articles for the invalid
        one; a 4xx on the first failure would hide which ones went through.
        """
        good = article_factory(status="draft")
        already = article_factory(status="draft")
        auth_client(editor).post(
            f"{BASE}/articles/{already.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )

        response = auth_client(editor).post(
            URL,
            {"slugs": [good.slug, already.slug], "transition": "publish"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["succeeded"] == 1 and body["failed"] == 1

        rows = {row["slug"]: row for row in body["results"]}
        assert rows[good.slug]["ok"] is True
        assert rows[already.slug]["ok"] is False
        assert rows[already.slug]["code"] == "illegal"

        good.refresh_from_db()
        assert good.status == "published"

    def test_unknown_slug_is_reported_not_fatal(
        self, auth_client, editor, article_factory
    ):
        article = article_factory(status="draft")
        body = auth_client(editor).post(
            URL,
            {"slugs": [article.slug, "no-such-article"], "transition": "publish"},
            format="json",
        ).json()
        rows = {row["slug"]: row for row in body["results"]}
        assert rows["no-such-article"]["code"] == "not_found"
        assert rows[article.slug]["ok"] is True

    def test_permission_failures_are_per_row(
        self, auth_client, writer, article_factory
    ):
        """An author may submit their own work but not publish it."""
        mine = article_factory(status="draft", author=writer)
        theirs = article_factory(status="draft")
        body = auth_client(writer).post(
            URL,
            {"slugs": [mine.slug, theirs.slug], "transition": "submit"},
            format="json",
        ).json()

        rows = {row["slug"]: row for row in body["results"]}
        assert rows[mine.slug]["ok"] is True
        # Not "forbidden": an author cannot see another author's draft at all,
        # so it is absent from their queryset entirely.
        assert rows[theirs.slug]["ok"] is False

        mine.refresh_from_db()
        theirs.refresh_from_db()
        assert mine.status == "in_review"
        assert theirs.status == "draft"

    def test_author_cannot_bulk_publish(self, auth_client, writer, article_factory):
        article = article_factory(status="draft", author=writer)
        body = auth_client(writer).post(
            URL, {"slugs": [article.slug], "transition": "publish"}, format="json"
        ).json()
        assert body["failed"] == 1
        assert body["results"][0]["code"] == "forbidden"
        article.refresh_from_db()
        assert article.status == "draft"

    def test_every_row_is_audited(self, auth_client, editor, article_factory):
        from apps.editorial.models import AuditLogEntry

        articles = [article_factory(status="draft") for _ in range(2)]
        auth_client(editor).post(
            URL,
            {"slugs": [a.slug for a in articles], "transition": "publish"},
            format="json",
        )
        for article in articles:
            entry = AuditLogEntry.objects.get(
                article=article, action="transition", to_state="published"
            )
            assert entry.metadata["source"] == "bulk"

    def test_batch_size_is_capped(self, auth_client, editor):
        response = auth_client(editor).post(
            URL,
            {"slugs": [f"a-{n}" for n in range(101)], "transition": "publish"},
            format="json",
        )
        assert response.status_code == 400

    def test_empty_selection_is_rejected(self, auth_client, editor):
        response = auth_client(editor).post(
            URL, {"slugs": [], "transition": "publish"}, format="json"
        )
        assert response.status_code == 400

    def test_publish_chain_runs_once_per_published_article(
        self,
        auth_client,
        editor,
        article_factory,
        stub_outbound_http,
        django_capture_on_commit_callbacks,
        settings,
    ):
        settings.CMS_REVALIDATE_SECRET = "test-secret"
        articles = [article_factory(status="draft") for _ in range(2)]
        with django_capture_on_commit_callbacks(execute=True):
            auth_client(editor).post(
                URL,
                {"slugs": [a.slug for a in articles], "transition": "publish"},
                format="json",
            )
        # One revalidation call per published article, not one for the batch.
        assert len(stub_outbound_http) == 2

    def test_is_tenant_scoped(
        self, auth_client, editor, article_factory, other_site, user_factory
    ):
        author = user_factory(role="author")
        mine = article_factory(status="draft")
        theirs = article_factory(status="draft", site=other_site, author=author)

        body = auth_client(editor).post(
            URL, {"slugs": [mine.slug, theirs.slug], "transition": "publish"}, format="json"
        ).json()
        rows = {row["slug"]: row for row in body["results"]}
        assert rows[theirs.slug]["code"] == "not_found"

        theirs.refresh_from_db()
        assert theirs.status == "draft"
