"""Translation groups and the hreflang alternates they produce."""

import pytest

from apps.articles.models import Article
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/public"


def _publish(article, site):
    Placement.objects.update_or_create(
        article=article,
        site=site,
        defaults={"is_primary": True, "is_live": True, "path_slug": article.slug},
    )
    return article


class TestTranslationGroups:
    def test_siblings_are_found_across_sites(
        self, article_factory, default_site, other_site
    ):
        english = article_factory(
            title="Machine translation", status="published", is_live=True,
            locale="en", translation_group="mt-2026",
        )
        bengali = Article.objects.create(
            site=other_site,
            title="যান্ত্রিক অনুবাদ",
            author=english.author,
            content={"blocks": []},
            status="published",
            is_live=True,
            locale="bn",
            translation_group="mt-2026",
        )

        # Cross-site by design: the Bengali edition may live on a different
        # tenant, and hreflang is precisely the tag that says they are the same
        # content in different languages.
        assert list(english.translations()) == [bengali]

    def test_an_article_without_a_group_has_no_siblings(self, article_factory):
        article = article_factory()
        assert list(article.translations()) == []

    def test_drafts_are_not_offered_as_translations(
        self, article_factory, default_site
    ):
        live = article_factory(
            status="published", is_live=True, translation_group="g"
        )
        article_factory(status="draft", translation_group="g")
        assert list(live.translations()) == []

    def test_locale_falls_back_to_the_site(self, article_factory, default_site):
        article = article_factory(locale="")
        assert article.effective_locale() == default_site.locale


class TestAlternates:
    def test_a_lone_article_gets_no_alternate_set(
        self, public_client, article_factory, default_site
    ):
        article = _publish(
            article_factory(status="published", is_live=True), default_site
        )
        body = public_client().get(f"{PUBLIC}/articles/{article.slug}/").json()
        # One entry means no cluster, and the front end emits no hreflang at
        # all -- a single self-referential alternate is noise.
        assert len(body["alternates"]) == 1
        assert body["alternates"][0]["is_current"] is True

    def test_the_set_is_self_referential(
        self, public_client, article_factory, default_site, other_site
    ):
        english = _publish(
            article_factory(
                status="published", is_live=True, locale="en",
                translation_group="pair",
            ),
            default_site,
        )
        bengali = Article.objects.create(
            site=other_site, title="Bengali edition", author=english.author,
            content={"blocks": []}, status="published", is_live=True,
            locale="bn", translation_group="pair",
        )
        _publish(bengali, other_site)

        body = public_client().get(f"{PUBLIC}/articles/{english.slug}/").json()
        locales = [entry["locale"] for entry in body["alternates"]]

        # Search engines require the set to include the page itself. Listing
        # only the *other* languages is the obvious thing to do and silently
        # disables the whole cluster.
        assert "en" in locales and "bn" in locales
        assert "x-default" in locales

    def test_x_default_points_at_the_current_page(
        self, public_client, article_factory, default_site, other_site
    ):
        english = _publish(
            article_factory(
                status="published", is_live=True, locale="en", translation_group="p2"
            ),
            default_site,
        )
        sibling = Article.objects.create(
            site=other_site, title="Other", author=english.author,
            content={"blocks": []}, status="published", is_live=True,
            locale="bn", translation_group="p2",
        )
        _publish(sibling, other_site)

        body = public_client().get(f"{PUBLIC}/articles/{english.slug}/").json()
        by_locale = {entry["locale"]: entry["url"] for entry in body["alternates"]}
        assert by_locale["x-default"] == by_locale["en"]

    def test_an_unplaced_translation_is_omitted(
        self, public_client, article_factory, default_site, other_site
    ):
        english = _publish(
            article_factory(
                status="published", is_live=True, locale="en", translation_group="p3"
            ),
            default_site,
        )
        unplaced = Article.objects.create(
            site=other_site, title="Unplaced", author=english.author,
            content={"blocks": []}, status="published", is_live=True,
            locale="bn", translation_group="p3",
        )
        # Creating an article auto-creates its primary placement, so this has
        # to be removed explicitly. Without a placement the article has no URL,
        # and advertising it as an alternate would point search engines at
        # nothing.
        unplaced.placements.all().delete()

        body = public_client().get(f"{PUBLIC}/articles/{english.slug}/").json()
        assert [e["locale"] for e in body["alternates"]] == ["en"]
