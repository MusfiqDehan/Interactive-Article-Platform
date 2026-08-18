"""Tests for the three-level SEO fallback chain."""

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.articles.models import Article
from apps.seo.models import SEOMetadata
from apps.seo.resolver import resolve_seo
from apps.syndication.models import Placement

pytestmark = pytest.mark.django_db


def seo_row(article, site=None, **fields):
    return SEOMetadata.objects.create(
        content_type=ContentType.objects.get_for_model(Article),
        object_id=article.pk,
        site=site,
        **fields,
    )


class TestFallbackChain:
    def test_computed_when_nothing_stored(self, article_factory, default_site):
        article = article_factory(title="My Title", excerpt="My excerpt.")
        seo = resolve_seo(article, site=default_site)
        assert seo.meta_title == "My Title"
        assert seo.meta_description == "My excerpt."

    def test_default_row_beats_computed(self, article_factory, default_site):
        article = article_factory(title="My Title")
        seo_row(article, meta_title="Stored Title")
        assert resolve_seo(article, site=default_site).meta_title == "Stored Title"

    def test_site_row_beats_default_row(self, article_factory, default_site):
        article = article_factory(title="My Title")
        seo_row(article, meta_title="Default Title")
        seo_row(article, site=default_site, meta_title="Site Title")
        assert resolve_seo(article, site=default_site).meta_title == "Site Title"

    def test_site_row_for_another_site_is_ignored(
        self, article_factory, default_site, other_site
    ):
        article = article_factory(title="My Title")
        seo_row(article, meta_title="Default Title")
        seo_row(article, site=other_site, meta_title="Partner Title")
        assert resolve_seo(article, site=default_site).meta_title == "Default Title"

    def test_blank_override_falls_through(self, article_factory, default_site):
        # An empty string means "not set", not "deliberately empty".
        article = article_factory(title="Computed Title")
        seo_row(article, site=default_site, meta_title="")
        assert resolve_seo(article, site=default_site).meta_title == "Computed Title"

    def test_description_falls_back_to_body_text(self, article_factory, default_site):
        article = article_factory(
            title="T",
            excerpt="",
            content={
                "blocks": [
                    {"type": "paragraph", "data": {"text": "The opening sentence. " * 20}}
                ]
            },
        )
        seo = resolve_seo(article, site=default_site)
        assert "The opening sentence" in seo.meta_description
        assert len(seo.meta_description) <= 160

    def test_description_falls_back_to_site_default(
        self, article_factory, default_site
    ):
        default_site.settings.default_meta_description = "Site-wide description."
        default_site.settings.save()
        article = article_factory(title="T", excerpt="", content={"blocks": []})
        assert (
            resolve_seo(article, site=default_site).meta_description
            == "Site-wide description."
        )


class TestBooleanHandling:
    def test_false_override_is_respected(self, article_factory, default_site):
        # Booleans need identity, not truthiness: robots_index=False is a real
        # setting and must not be treated as "unset".
        article = article_factory()
        seo_row(article, site=default_site, robots_index=False)
        assert resolve_seo(article, site=default_site).robots_index is False

    def test_defaults_to_indexable(self, article_factory, default_site):
        assert resolve_seo(article_factory(), site=default_site).robots_index is True


class TestSocialInheritance:
    def test_og_inherits_from_meta(self, article_factory, default_site):
        article = article_factory(title="Shared", excerpt="Description here.")
        seo = resolve_seo(article, site=default_site)
        assert seo.og_title == "Shared"
        assert seo.og_description == "Description here."

    def test_og_can_be_overridden(self, article_factory, default_site):
        article = article_factory(title="Shared")
        seo_row(article, site=default_site, og_title="Social Headline")
        seo = resolve_seo(article, site=default_site)
        assert seo.og_title == "Social Headline"
        assert seo.meta_title == "Shared"  # unaffected

    def test_twitter_image_inherits_og_image(self, article_factory, default_site):
        article = article_factory(featured_image="https://cdn/x.png")
        seo = resolve_seo(article, site=default_site)
        assert seo.og_image == "https://cdn/x.png"
        assert seo.twitter_image == "https://cdn/x.png"


class TestCanonical:
    def test_primary_placement_self_canonicalises(self, article_factory, default_site):
        article = article_factory(status="published")
        placement = Placement.objects.get(article=article, is_primary=True)
        seo = resolve_seo(article, site=default_site, placement=placement)
        assert seo.canonical_url == placement.url

    def test_syndicated_placement_points_home(
        self, article_factory, default_site, other_site
    ):
        # The single biggest duplicate-content lever in the design.
        article = article_factory(status="published")
        primary = Placement.objects.get(article=article, is_primary=True)
        syndicated = Placement.objects.create(
            article=article, site=other_site, path_slug="copy",
            is_live=True, canonical_to_primary=True,
        )
        seo = resolve_seo(article, site=other_site, placement=syndicated)
        assert seo.canonical_url == primary.url

    def test_explicit_canonical_wins(self, article_factory, default_site):
        article = article_factory(status="published")
        placement = Placement.objects.get(article=article, is_primary=True)
        seo_row(article, site=default_site, canonical_url="https://elsewhere.test/x")
        seo = resolve_seo(article, site=default_site, placement=placement)
        assert seo.canonical_url == "https://elsewhere.test/x"


class TestUniqueness:
    def test_only_one_default_row_per_object(self, article_factory):
        from django.db import IntegrityError, transaction

        article = article_factory()
        seo_row(article)
        # SQL treats NULLs as distinct, so this needs its own partial index.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                seo_row(article)

    def test_one_row_per_object_per_site(self, article_factory, default_site):
        from django.db import IntegrityError, transaction

        article = article_factory()
        seo_row(article, site=default_site)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                seo_row(article, site=default_site)
