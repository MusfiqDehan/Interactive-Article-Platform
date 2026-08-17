"""Tests for the public delivery API.

The headline behaviour: the *same* article, fetched through two different API
keys, must come back with two different canonical URLs -- the syndicated copy
pointing home to its owning site. That is the duplicate-content lever the whole
multi-site design rests on.
"""

import pytest

from apps.articles.models import Article
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db

BASE = "/api/v1/public"


@pytest.fixture
def published(article_factory):
    def _make(**kwargs):
        kwargs.setdefault("status", "published")
        article = article_factory(**kwargs)
        Placement.objects.filter(article=article).update(is_live=True)
        return article

    return _make


class TestArticleList:
    def test_lists_live_articles(self, public_client, published):
        published(title="Live One")
        body = public_client().get(f"{BASE}/articles/").json()
        assert [r["title"] for r in body["results"]] == ["Live One"]

    def test_drafts_are_excluded(self, public_client, article_factory):
        article_factory(title="A Draft", status="draft")
        assert public_client().get(f"{BASE}/articles/").json()["results"] == []

    def test_unpublishing_removes_it_from_the_feed(self, public_client, published):
        article = published(title="Temporarily Live")
        client = public_client()
        assert len(client.get(f"{BASE}/articles/").json()["results"]) == 1

        article.status = "draft"
        article.save()  # signal syncs the placement's is_live

        assert client.get(f"{BASE}/articles/").json()["results"] == []

    def test_uses_cursor_pagination(self, public_client, published):
        for i in range(15):
            published(title=f"Article {i}")
        body = public_client().get(f"{BASE}/articles/").json()
        assert len(body["results"]) == 12
        # Cursor, not page-number: no `count`, and `next` is an opaque cursor.
        assert body["next"] is not None
        assert "count" not in body

    def test_views_count_is_not_exposed(self, public_client, published):
        published(title="X")
        row = public_client().get(f"{BASE}/articles/").json()["results"][0]
        # It changes on every request and would make responses uncacheable.
        assert "views_count" not in row

    def test_filter_by_category(self, public_client, published, category_factory):
        tech = category_factory(name="Tech")
        published(title="In Tech", category=tech)
        published(title="Uncategorised")

        body = public_client().get(f"{BASE}/articles/?category={tech.slug}").json()
        assert [r["title"] for r in body["results"]] == ["In Tech"]

    def test_search(self, public_client, published):
        published(title="Bengali Translation")
        published(title="Something Else")
        body = public_client().get(f"{BASE}/articles/?q=Translation").json()
        assert [r["title"] for r in body["results"]] == ["Bengali Translation"]

    def test_featured_action(self, public_client, published):
        published(title="Featured", is_featured=True)
        published(title="Ordinary")
        body = public_client().get(f"{BASE}/articles/featured/").json()
        assert [r["title"] for r in body] == ["Featured"]


class TestArticleDetail:
    def test_detail_includes_content_and_annotations(self, public_client, published):
        article = published(
            title="Annotated",
            content={
                "blocks": [
                    {
                        "id": "b1",
                        "type": "interactive_text",
                        "data": {
                            "text": '<span data-annotation-id="a1">term</span>',
                            "annotations": [
                                {
                                    "id": "a1",
                                    "type": "text",
                                    "modal_title": "Definition",
                                    "modal_content": "<p>Explained</p>",
                                }
                            ],
                        },
                    }
                ]
            },
        )
        placement = Placement.objects.get(article=article, is_primary=True)
        body = public_client().get(f"{BASE}/articles/{placement.path_slug}/").json()

        assert body["content"]["blocks"]
        # annotations_index is what lets the front-end server-render annotation
        # bodies instead of hiding them behind a click.
        (annotation,) = body["annotations_index"]
        assert annotation["title"] == "Definition"
        assert annotation["plain"] == "Explained"
        assert annotation["label"] == "term"

    def test_detail_includes_category_path(self, public_client, published, category_factory):
        tech = category_factory(name="Tech")
        article = published(title="Pathed", category=tech)
        placement = Placement.objects.get(article=article, is_primary=True)
        body = public_client().get(f"{BASE}/articles/{placement.path_slug}/").json()
        # `url_path` joined the trail with the category tree: a breadcrumb has
        # to link somewhere, and for a nested category that link is the whole
        # ancestor path, not the leaf slug.
        assert body["category_path"] == [
            {
                "id": tech.id,
                "name": "Tech",
                "slug": tech.slug,
                "url_path": tech.url_path,
            }
        ]

    def test_unicode_slug_detail(self, public_client, published):
        article = published(title="যান্ত্রিক অনুবাদ")
        placement = Placement.objects.get(article=article, is_primary=True)
        assert placement.path_slug == "যান্ত্রিক-অনুবাদ"
        response = public_client().get(f"{BASE}/articles/{placement.path_slug}/")
        assert response.status_code == 200

    def test_missing_slug_is_404(self, public_client):
        assert public_client().get(f"{BASE}/articles/nope/").status_code == 404


class TestSyndicatedCanonical:
    """The core multi-site guarantee."""

    def test_same_article_two_sites_two_canonicals(
        self, public_client, published, other_site
    ):
        article = published(title="Syndicated")
        primary = Placement.objects.get(article=article, is_primary=True)

        # Place the same article on the partner site under a different path.
        Placement.objects.create(
            article=article,
            site=other_site,
            path_slug="syndicated-copy",
            is_primary=False,
            is_live=True,
            canonical_to_primary=True,
            published_at=article.published_at,
        )

        home = public_client().get(f"{BASE}/articles/{primary.path_slug}/").json()
        away = public_client(other_site).get(f"{BASE}/articles/syndicated-copy/").json()

        # Different URLs on each site...
        assert home["url"] != away["url"]
        assert away["slug"] == "syndicated-copy"
        # ...but the syndicated copy points its canonical back at the owner.
        assert home["canonical_url"] == home["url"]
        assert away["canonical_url"] == home["url"]

    def test_self_canonical_when_opted_out(self, public_client, published, other_site):
        article = published(title="Independent")
        Placement.objects.create(
            article=article,
            site=other_site,
            path_slug="independent",
            is_live=True,
            canonical_to_primary=False,
            published_at=article.published_at,
        )
        away = public_client(other_site).get(f"{BASE}/articles/independent/").json()
        assert away["canonical_url"] == away["url"]

    def test_placement_can_override_title(self, public_client, published, other_site):
        article = published(title="Original Title")
        Placement.objects.create(
            article=article,
            site=other_site,
            path_slug="overridden",
            is_live=True,
            override_title="Partner Headline",
            published_at=article.published_at,
        )
        away = public_client(other_site).get(f"{BASE}/articles/overridden/").json()
        assert away["title"] == "Partner Headline"


class TestSlugsAndSite:
    def test_slugs_endpoint_is_unpaginated(self, public_client, published):
        for i in range(15):
            published(title=f"Article {i}")
        body = public_client().get(f"{BASE}/articles/slugs/").json()
        # Feeds generateStaticParams and the sitemap, so it must be complete.
        assert isinstance(body, list)
        assert len(body) == 15
        assert set(body[0]) == {"slug", "updated_at", "published_at"}

    def test_site_endpoint(self, public_client, default_site):
        body = public_client().get(f"{BASE}/site/").json()
        assert body["slug"] == default_site.slug
        assert body["base_url"] == default_site.base_url
        # The revalidation secret must never reach a browser.
        assert "revalidate_secret" not in body

    def test_categories_endpoint(self, public_client, category_factory):
        category_factory(name="Tech")
        body = public_client().get(f"{BASE}/categories/").json()
        assert [c["name"] for c in body] == ["Tech"]

    def test_health_needs_no_key(self, api_client):
        assert api_client.get(f"{BASE}/health/").status_code == 200


class TestCachingHeaders:
    def test_cache_control_and_etag(self, public_client, published):
        published(title="Cached")
        response = public_client().get(f"{BASE}/articles/")
        assert "s-maxage" in response["Cache-Control"]
        assert "stale-while-revalidate" in response["Cache-Control"]
        assert response["ETag"].startswith('W/"')

    def test_vary_includes_api_key(self, public_client, published):
        published(title="Cached")
        # Without this a shared cache could serve one tenant's body to another.
        assert "X-API-Key" in public_client().get(f"{BASE}/articles/")["Vary"]

    def test_etag_changes_when_content_version_bumps(self, public_client, published):
        published(title="Cached")
        client = public_client()
        first = client.get(f"{BASE}/articles/")["ETag"]

        from common.cache import bump_content_version
        from apps.tenancy.models import Site

        bump_content_version(Site.objects.get(is_default=True).pk)

        assert client.get(f"{BASE}/articles/")["ETag"] != first

    def test_conditional_request_returns_304(self, public_client, published):
        article = published(title="Cached")
        placement = Placement.objects.get(article=article, is_primary=True)
        client = public_client()
        url = f"{BASE}/articles/{placement.path_slug}/"

        etag = client.get(url)["ETag"]
        assert client.get(url, HTTP_IF_NONE_MATCH=etag).status_code == 304


class TestReadOnly:
    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_writes_are_rejected(self, public_client, published, method):
        article = published(title="Immutable")
        placement = Placement.objects.get(article=article, is_primary=True)
        client = public_client()
        response = getattr(client, method)(
            f"{BASE}/articles/{placement.path_slug}/", {}, format="json"
        )
        assert response.status_code in (403, 405)
