"""Tests for redirects, including the automatic 301 on slug change."""

import pytest

from apps.seo.models import Redirect
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db


class TestNormalisation:
    def test_leading_slash_is_added(self, default_site):
        r = Redirect.objects.create(
            site=default_site, source_path="old-page", target_path="new-page"
        )
        assert r.source_path == "/old-page"
        assert r.target_path == "/new-page"

    def test_trailing_slash_is_stripped(self, default_site):
        r = Redirect.objects.create(
            site=default_site, source_path="/old/", target_path="/new/"
        )
        assert r.source_path == "/old"
        assert r.target_path == "/new"

    def test_absolute_target_is_left_alone(self, default_site):
        r = Redirect.objects.create(
            site=default_site, source_path="/old", target_path="https://elsewhere.test/x"
        )
        assert r.target_path == "https://elsewhere.test/x"


class TestAutomaticSlugRedirect:
    def test_slug_change_on_live_article_creates_a_301(self, article_factory):
        article = article_factory(title="Original Title", status="published")
        original_slug = article.slug

        article.slug = ""
        article.title = "Brand New Title"
        article.save()

        redirect = Redirect.objects.get(source_path=f"/articles/{original_slug}")
        assert redirect.target_path == f"/articles/{article.slug}"
        assert redirect.status_code == 301

    def test_draft_slug_change_creates_nothing(self, article_factory):
        # The old URL was never public, so a redirect would just be noise.
        article = article_factory(title="Draft Title", status="draft")
        article.slug = "a-different-slug"
        article.save()
        assert Redirect.objects.count() == 0

    def test_no_redirect_when_slug_is_unchanged(self, article_factory):
        article = article_factory(status="published")
        article.excerpt = "Edited body, same slug."
        article.save()
        assert Redirect.objects.count() == 0

    def test_renaming_twice_does_not_create_a_chain(self, article_factory):
        # A -> B -> C must collapse to A -> C and B -> C; crawlers should never
        # have to walk a chain.
        article = article_factory(title="First", status="published")
        slug_a = article.slug

        article.slug = ""
        article.title = "Second"
        article.save()
        slug_b = article.slug

        article.slug = ""
        article.title = "Third"
        article.save()
        slug_c = article.slug

        assert (
            Redirect.objects.get(source_path=f"/articles/{slug_a}").target_path
            == f"/articles/{slug_c}"
        )
        assert (
            Redirect.objects.get(source_path=f"/articles/{slug_b}").target_path
            == f"/articles/{slug_c}"
        )

    def test_reverting_a_slug_removes_the_self_redirect(self, article_factory):
        # Renaming A->B then back to A would otherwise leave /A -> /A.
        article = article_factory(title="Original", status="published")
        slug_a = article.slug

        article.slug = ""
        article.title = "Renamed"
        article.save()

        article.slug = slug_a
        article.save()

        assert not Redirect.objects.filter(
            source_path=f"/articles/{slug_a}", target_path=f"/articles/{slug_a}"
        ).exists()


class TestPublicRedirectsEndpoint:
    def test_lists_active_redirects(self, public_client, default_site):
        Redirect.objects.create(
            site=default_site, source_path="/old", target_path="/new"
        )
        Redirect.objects.create(
            site=default_site, source_path="/gone", target_path="/x", is_active=False
        )
        body = public_client().get("/api/v1/public/redirects/").json()
        assert [r["source_path"] for r in body] == ["/old"]

    def test_scoped_to_the_calling_site(self, public_client, default_site, other_site):
        Redirect.objects.create(site=other_site, source_path="/theirs", target_path="/x")
        assert public_client().get("/api/v1/public/redirects/").json() == []


class TestLoopDetection:
    def test_self_redirect_is_rejected(self, auth_client, admin, default_site):
        response = auth_client(admin).post(
            "/api/v1/studio/redirects/",
            {"source_path": "/loop", "target_path": "/loop"},
            format="json",
        )
        assert response.status_code == 400

    def test_cycle_is_rejected(self, auth_client, admin, default_site):
        Redirect.objects.create(site=default_site, source_path="/b", target_path="/a")
        # /a -> /b would complete the cycle a -> b -> a.
        response = auth_client(admin).post(
            "/api/v1/studio/redirects/",
            {"source_path": "/a", "target_path": "/b"},
            format="json",
        )
        assert response.status_code == 400
        assert "loop" in str(response.json()).lower()

    def test_valid_chain_is_allowed(self, auth_client, admin, default_site):
        Redirect.objects.create(site=default_site, source_path="/b", target_path="/c")
        response = auth_client(admin).post(
            "/api/v1/studio/redirects/",
            {"source_path": "/a", "target_path": "/b"},
            format="json",
        )
        assert response.status_code == 201
