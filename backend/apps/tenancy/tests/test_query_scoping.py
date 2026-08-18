"""SQL-level proof that tenant scoping actually reaches the database.

``TenantModel`` makes scoping easy and ``TenantScopedViewSetMixin`` makes it
hard to skip; these tests prove it happened, by inspecting the SQL that ran.
"""

import pytest

from apps.articles.models import Article
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db


@pytest.fixture
def live_article(article_factory):
    article = article_factory(status="published")
    Placement.objects.filter(article=article).update(is_live=True)
    return article


class TestFixtureItself:
    """The detector must actually detect; otherwise the tests below prove nothing."""

    def test_unscoped_query_is_caught(self, assert_queries_scoped, live_article):
        with pytest.raises(AssertionError, match="unscoped"):
            with assert_queries_scoped():
                list(Article.unscoped.all())

    def test_scoped_query_passes(self, assert_queries_scoped, live_article, default_site):
        with assert_queries_scoped():
            list(Article.objects.for_site(default_site))


class TestEndpointsAreScoped:
    def test_public_article_list(self, assert_queries_scoped, public_client, live_article):
        with assert_queries_scoped():
            assert public_client().get("/api/v1/public/articles/").status_code == 200

    def test_public_article_detail(self, assert_queries_scoped, public_client, live_article):
        placement = Placement.objects.get(article=live_article, is_primary=True)
        with assert_queries_scoped():
            response = public_client().get(
                f"/api/v1/public/articles/{placement.path_slug}/"
            )
        assert response.status_code == 200

    def test_public_categories(self, assert_queries_scoped, public_client, category_factory):
        category_factory()
        with assert_queries_scoped():
            assert public_client().get("/api/v1/public/categories/").status_code == 200

    def test_studio_article_list(self, assert_queries_scoped, auth_client, admin, live_article):
        with assert_queries_scoped():
            assert auth_client(admin).get("/api/v1/studio/articles/").status_code == 200

    def test_studio_media_list(self, assert_queries_scoped, auth_client, admin):
        with assert_queries_scoped():
            assert auth_client(admin).get("/api/v1/studio/media/").status_code == 200

