"""Cross-tenant isolation.

The property under test: content owned by one site must never be reachable
through another site's credentials, on any surface.
"""

import pytest

from apps.articles.models import Article
from apps.categories.models import Category
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_site_content(default_site, other_site, author):
    """One published article on each site, each with a live primary placement."""
    ours = Article.objects.create(
        title="Our Article", site=default_site, author=author, status="published"
    )
    theirs = Article.objects.create(
        title="Their Article", site=other_site, author=author, status="published"
    )
    # The post_save signal creates primary placements; make them live.
    Placement.objects.filter(article__in=[ours, theirs]).update(is_live=True)
    return ours, theirs


class TestManagerScoping:
    def test_for_site_filters(self, two_site_content, default_site, other_site):
        ours, theirs = two_site_content
        assert list(Article.objects.for_site(default_site)) == [ours]
        assert list(Article.objects.for_site(other_site)) == [theirs]

    def test_for_site_none_returns_empty(self, two_site_content):
        assert list(Article.objects.for_site(None)) == []

    def test_unscoped_sees_everything(self, two_site_content):
        assert Article.unscoped.count() == 2

    def test_categories_are_scoped(self, default_site, other_site):
        ours = Category.objects.create(name="Tech", site=default_site)
        theirs = Category.objects.create(name="Tech", site=other_site)
        # Same name on both sites is legal now that uniqueness is per-site.
        assert list(Category.objects.for_site(default_site)) == [ours]
        assert list(Category.objects.for_site(other_site)) == [theirs]


class TestPublicApiIsolation:
    def test_key_only_sees_its_own_site(self, public_client, two_site_content):
        ours, theirs = two_site_content
        body = public_client().get("/api/v1/public/articles/").json()
        titles = [row["title"] for row in body["results"]]
        assert titles == ["Our Article"]

    def test_other_key_sees_the_other_site(
        self, public_client, two_site_content, other_site
    ):
        body = public_client(other_site).get("/api/v1/public/articles/").json()
        assert [row["title"] for row in body["results"]] == ["Their Article"]

    def test_cannot_fetch_another_sites_article_by_slug(
        self, public_client, two_site_content
    ):
        _, theirs = two_site_content
        placement = Placement.objects.get(article=theirs, is_primary=True)
        response = public_client().get(
            f"/api/v1/public/articles/{placement.path_slug}/"
        )
        assert response.status_code == 404

    def test_missing_api_key_is_rejected(self, api_client, two_site_content):
        assert api_client.get("/api/v1/public/articles/").status_code in (401, 403)

    def test_invalid_api_key_is_rejected(self, api_client, two_site_content):
        api_client.credentials(HTTP_X_API_KEY="ia_live_nonsense")
        assert api_client.get("/api/v1/public/articles/").status_code in (401, 403)

    def test_scope_is_enforced(self, api_client, api_key_factory, default_site, two_site_content):
        # A key without read:taxonomy must not reach the categories route.
        _, raw = api_key_factory(default_site, scopes=["read:content"])
        api_client.credentials(HTTP_X_API_KEY=raw)
        assert api_client.get("/api/v1/public/articles/").status_code == 200
        assert api_client.get("/api/v1/public/categories/").status_code == 403


class TestStudioIsolation:
    def test_studio_lists_only_the_resolved_site(
        self, auth_client, admin, two_site_content, default_site
    ):
        client = auth_client(admin)
        body = client.get("/api/v1/studio/articles/").json()
        assert [row["title"] for row in body["results"]] == ["Our Article"]

    def test_site_header_switches_tenant(
        self, auth_client, admin, two_site_content, other_site
    ):
        client = auth_client(admin)
        body = client.get(
            "/api/v1/studio/articles/", HTTP_X_CMS_SITE=other_site.slug
        ).json()
        assert [row["title"] for row in body["results"]] == ["Their Article"]

    def test_non_member_cannot_reach_a_site(
        self, auth_client, author, two_site_content, other_site
    ):
        # A plain author with no membership anywhere gets nothing.
        client = auth_client(author)
        response = client.get(
            "/api/v1/studio/articles/", HTTP_X_CMS_SITE=other_site.slug
        )
        assert response.status_code == 403

    def test_member_can_reach_their_site(
        self, auth_client, author, membership_factory, two_site_content, other_site
    ):
        membership_factory(author, other_site, role="author")
        client = auth_client(author)
        response = client.get(
            "/api/v1/studio/articles/", HTTP_X_CMS_SITE=other_site.slug
        )
        assert response.status_code == 200
