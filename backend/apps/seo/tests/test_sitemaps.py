import pytest

from apps.seo.sitemaps import STATIC_PAGES, shard_entries, shard_index

pytestmark = pytest.mark.django_db


class TestSitemapIncludesSurfaces:
    def test_empty_site_still_emits_static_pages(self, default_site):
        shards = shard_index(default_site)
        assert shards[0]["n"] == 0
        assert shards[0]["count"] >= len(STATIC_PAGES)

        urls = {entry["url"] for entry in shard_entries(default_site, 0)}
        assert default_site.url_for("") in urls
        assert default_site.url_for("home") in urls
        assert default_site.url_for("articles") in urls
        assert default_site.url_for("llms.txt") in urls

    def test_categories_and_live_articles_are_listed(
        self, default_site, category_factory, article_factory
    ):
        category_factory(name="Astronomy")
        article = article_factory(title="Jupiter's quiet geometry", status="published")

        urls = {entry["url"] for entry in shard_entries(default_site, 0)}
        assert any("/categories/astronomy" in url for url in urls)
        assert any(article.slug in url for url in urls)

    def test_hidden_articles_are_omitted(self, default_site, article_factory):
        live = article_factory(title="Public piece", status="published")
        hidden = article_factory(title="Hidden piece", status="archived")

        urls = " ".join(entry["url"] for entry in shard_entries(default_site, 0))
        assert live.slug in urls
        assert hidden.slug not in urls
