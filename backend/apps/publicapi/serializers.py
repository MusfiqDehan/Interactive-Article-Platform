"""Serializers for the public delivery API.

Shapes here are driven by what a server-rendering front-end needs in one round
trip: resolved SEO-ish fields, the canonical URL for this placement, the
category path for breadcrumbs, and -- critically -- ``annotations_index``, so
interactive annotation content can be server-rendered instead of appearing only
on click.

``views_count`` is deliberately absent. It changes on every request and would
make every response uncacheable; it moves to a separate stats endpoint.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.articles.models import Article
from apps.categories.models import Category
from apps.syndication.models import Placement
from apps.taxonomy.models import Tag, tags_for
from apps.tenancy.models import Site, SiteSettings
from common.blocks import extract_annotations


class PublicAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    username = serializers.CharField()
    avatar = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else None


class PublicCategorySerializer(serializers.ModelSerializer):
    article_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = (
            "id", "name", "slug", "description", "order",
            "parent", "url_path", "depth", "article_count",
        )


class PublicTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "kind", "description", "usage_count")


class PlacementMixin:
    """Placement-derived fields shared by the list and detail serializers.

    ``self.instance`` is a Placement in these serializers, with the article
    reachable through it -- which is what lets the same article render with a
    different path and canonical on each site.
    """

    def get_slug(self, placement):
        return placement.path_slug

    def get_title(self, placement):
        return placement.override_title or placement.article.title

    def get_excerpt(self, placement):
        return placement.override_excerpt or placement.article.excerpt

    def get_url(self, placement):
        return placement.url

    def get_canonical_url(self, placement):
        return placement.resolved_canonical()


class PublicArticleListSerializer(PlacementMixin, serializers.Serializer):
    id = serializers.IntegerField(source="article.id")
    slug = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    canonical_url = serializers.SerializerMethodField()
    featured_image = serializers.CharField(source="article.featured_image")
    reading_time = serializers.IntegerField(source="article.reading_time")
    word_count = serializers.IntegerField(source="article.word_count")
    locale = serializers.SerializerMethodField()
    is_featured = serializers.BooleanField(source="article.is_featured")
    published_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField(source="article.updated_at")
    author = PublicAuthorSerializer(source="article.author")
    category = PublicCategorySerializer(source="article.category")

    def get_locale(self, placement):
        return placement.site.locale


class PublicArticleDetailSerializer(PublicArticleListSerializer):
    content = serializers.JSONField(source="article.content")
    seo = serializers.SerializerMethodField()
    category_path = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    alternates = serializers.SerializerMethodField()
    annotations_index = serializers.SerializerMethodField()
    site = serializers.SerializerMethodField()

    def get_seo(self, placement):
        """Fully resolved metadata for *this* placement.

        Everything the front-end needs for generateMetadata in one payload:
        title, description, canonical, robots directives, OG/Twitter cards and
        structured-data hints -- already resolved through the per-site >
        default > computed fallback chain.
        """
        from apps.seo.resolver import resolve_seo

        return resolve_seo(
            placement.article, site=placement.site, placement=placement
        ).as_dict()

    def get_category_path(self, placement):
        """Root-to-leaf trail, for BreadcrumbList structured data.

        Walks the tree from the article's category up to the root, so
        reparenting a category updates every breadcrumb that passes through it.
        One FK, any depth -- the old flat ``category``/``subcategory`` pair
        could not express a trail longer than two steps.
        """
        leaf = placement.article.category
        if leaf is None:
            return []
        return [
            {
                "id": node.id,
                "name": node.name,
                "slug": node.slug,
                "url_path": node.url_path,
            }
            for node in [*leaf.ancestors(), leaf]
        ]

    def get_tags(self, placement):
        return [
            {"name": tag.name, "slug": tag.slug, "kind": tag.kind}
            for tag in tags_for(placement.article)
        ]

    def get_alternates(self, placement):
        """`hreflang` alternates for this article.

        Includes **this** article as well as its translations. That is the rule
        search engines actually require: a set of alternates must be
        self-referential and mutually consistent, or the whole cluster is
        ignored -- so listing only the *other* languages, which reads as the
        obvious thing to do, silently disables the feature.

        `x-default` points at the owning site's copy, which is where a reader
        whose language we do not publish should land.
        """
        article = placement.article
        entries = [
            {
                "locale": article.effective_locale(),
                "url": placement.url,
                "is_current": True,
            }
        ]
        for sibling in article.translations():
            primary = sibling.placements.filter(is_primary=True).select_related(
                "site"
            ).first()
            if primary is None:
                continue
            entries.append(
                {
                    "locale": sibling.effective_locale(),
                    "url": primary.url,
                    "is_current": False,
                }
            )
        if len(entries) > 1:
            entries.append({"locale": "x-default", "url": entries[0]["url"], "is_current": False})
        return entries

    def get_annotations_index(self, placement):
        """Every annotation, hotspot and chapter, in reading order.

        Lets the front-end server-render annotation bodies into a <details>
        appendix so their content is in the HTML for crawlers and no-JS
        readers, instead of only materialising inside a modal on click.
        """
        return extract_annotations(placement.article.content)

    def get_site(self, placement):
        return {
            "slug": placement.site.slug,
            "name": placement.site.name,
            "base_url": placement.site.base_url,
            "locale": placement.site.locale,
        }


class SlugEntrySerializer(serializers.Serializer):
    """Minimal payload for generateStaticParams and sitemap generation."""

    slug = serializers.CharField(source="path_slug")
    updated_at = serializers.DateTimeField(source="article.updated_at")
    published_at = serializers.DateTimeField()


class PublicSiteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="site.name")
    slug = serializers.CharField(source="site.slug")
    base_url = serializers.CharField(source="site.base_url")
    locale = serializers.CharField(source="site.locale")

    class Meta:
        model = SiteSettings
        fields = (
            "name", "slug", "base_url", "locale",
            "site_title", "title_template", "default_meta_description",
            "default_og_image", "organization_jsonld", "robots_extra",
            "google_site_verification", "allow_ai_crawlers",
        )


# ---------------------------------------------------------------------------
# Response shapes for endpoints that return plain dicts.
#
# These exist so the endpoints appear in the OpenAPI schema at all. Without a
# declared response, drf-spectacular logs "unable to guess serializer" and
# *silently drops the path* -- so the generated TypeScript client simply would
# not know these routes exist.
# ---------------------------------------------------------------------------


class RedirectRuleSerializer(serializers.Serializer):
    source_path = serializers.CharField()
    target_path = serializers.CharField()
    status_code = serializers.IntegerField()
    is_regex = serializers.BooleanField()


class SitemapEntrySerializer(serializers.Serializer):
    url = serializers.CharField()
    lastmod = serializers.CharField(required=False, allow_null=True)
    changefreq = serializers.CharField(required=False, allow_null=True)
    priority = serializers.FloatField(required=False, allow_null=True)
    image = serializers.CharField(required=False, allow_null=True)


class SitemapShardSerializer(serializers.Serializer):
    n = serializers.IntegerField()
    count = serializers.IntegerField(required=False)
    lastmod = serializers.CharField(required=False, allow_null=True)


class SitemapIndexSerializer(serializers.Serializer):
    shards = SitemapShardSerializer(many=True)


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
