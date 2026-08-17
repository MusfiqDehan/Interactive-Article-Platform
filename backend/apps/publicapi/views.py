"""Public delivery API (``/api/v1/public/``).

Read-only, API-key authenticated, tenant-scoped. Every route resolves content
through ``syndication.Placement`` rather than ``Article`` directly, which is
what makes the same article render with a different path and a different
canonical URL on each site it is placed on.

Responses carry a content-version ETag and ``stale-while-revalidate``, so a
front-end CDN can serve cached HTML while refreshing in the background.
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.articles.models import Article
from apps.categories.models import Category
from apps.syndication.models import Placement
from apps.taxonomy.models import Tag, TaggedItem
from apps.tenancy.models import SiteSettings
from common.cache import etag_for
from common.pagination import PublicCursorPagination
from common.permissions import HasValidApiKey
from common.throttles import ApiKeyRateThrottle
from common.views import BaseAPIView

from .serializers import (
    HealthSerializer,
    PublicArticleDetailSerializer,
    PublicArticleListSerializer,
    PublicCategorySerializer,
    PublicSiteSerializer,
    PublicTagSerializer,
    RedirectRuleSerializer,
    SitemapEntrySerializer,
    SitemapIndexSerializer,
    SlugEntrySerializer,
)

# 60s at the edge, but a stale copy may be served for 10 minutes while the CDN
# refreshes -- so a publish is visible quickly without a thundering herd.
CACHE_CONTROL = "public, s-maxage=60, stale-while-revalidate=600"


class PublicAPIMixin:
    permission_classes = (HasValidApiKey,)
    throttle_classes = (ApiKeyRateThrottle,)
    authentication_classes = ()  # API key only; no session/JWT on this surface

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.method in ("GET", "HEAD") and response.status_code == 200:
            site = getattr(request, "site", None)
            if site is not None:
                response["Cache-Control"] = CACHE_CONTROL
                response["ETag"] = etag_for(site.pk, self._etag_suffix(request))
                response["Vary"] = "X-API-Key, Accept-Encoding"
        return response

    def _etag_suffix(self, request) -> str:
        from common.cache import query_hash

        return query_hash(path=request.path, query=request.GET.dict())

    def check_not_modified(self, request, response):
        """Return 304 when the client's ETag still matches."""
        if request.headers.get("If-None-Match") == response.get("ETag"):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        return response


class PlacementQuerysetMixin:
    """Live placements for the calling tenant, with the shared query filters."""

    required_scope = "read:content"

    def placements(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return Placement.objects.none()
        return (
            Placement.objects.live()
            .for_site(site)
            .select_related(
                "article",
                "article__author",
                "article__category",
                "site",
            )
        )

    def filtered_placements(self):
        queryset = self.placements()
        params = self.request.query_params
        if category := params.get("category"):
            queryset = queryset.filter(article__category__slug=category)
        if featured := params.get("featured"):
            if featured.lower() in ("1", "true", "yes"):
                queryset = queryset.filter(article__is_featured=True)
        if search := params.get("q"):
            queryset = queryset.filter(
                Q(article__title__icontains=search)
                | Q(article__excerpt__icontains=search)
                | Q(article__plain_text__icontains=search)
            )
        for slug in params.getlist("tag"):
            if not slug:
                continue
            queryset = queryset.filter(
                article__pk__in=TaggedItem.objects.filter(
                    content_type=ContentType.objects.get_for_model(Article),
                    tag__slug=slug,
                ).values("object_id")
            )
        return queryset


@extend_schema(tags=["Public"])
class PublicArticleListView(PublicAPIMixin, PlacementQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/articles/"""

    serializer_class = PublicArticleListSerializer
    pagination_class = PublicCursorPagination
    # Query filtering is hand-written above; the DRF backends would need a
    # FilterSet over Placement to express the same joins.
    filter_backends = ()

    def get_queryset(self):
        return self.filtered_placements()

    def get(self, request):
        return self.list_response(self.get_queryset(), filter=False)


@extend_schema(tags=["Public"], responses=SlugEntrySerializer(many=True))
class PublicArticleSlugsView(PublicAPIMixin, PlacementQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/articles/slugs/

    Feeds ``generateStaticParams`` and sitemap generation, so it is deliberately
    unpaginated and minimal.
    """

    serializer_class = SlugEntrySerializer
    pagination_class = None

    def get(self, request):
        site = getattr(request, "site", None)
        if site is None:
            return Response([])
        # Built fresh rather than narrowing the shared `placements()` helper:
        # that helper select_relates author and category, and combining a
        # select_related with an `.only()` that omits those relations raises
        # FieldError. This endpoint feeds generateStaticParams and sitemaps, so
        # loading whole articles to emit slugs would be wasteful anyway.
        queryset = (
            Placement.objects.live()
            .for_site(site)
            .select_related("article")
            .only("path_slug", "published_at", "article__updated_at")
            .order_by("-published_at")
        )
        return Response(SlugEntrySerializer(queryset, many=True).data)


@extend_schema(tags=["Public"])
class PublicFeaturedArticlesView(PublicAPIMixin, PlacementQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/articles/featured/ -- unpaginated, by contract."""

    serializer_class = PublicArticleListSerializer
    pagination_class = None

    def get(self, request):
        queryset = self.filtered_placements().filter(article__is_featured=True)[:6]
        return Response(PublicArticleListSerializer(queryset, many=True).data)


@extend_schema(tags=["Public"])
class PublicArticleDetailView(PublicAPIMixin, PlacementQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/articles/{slug}/"""

    serializer_class = PublicArticleDetailSerializer
    pagination_class = None
    lookup_field = "path_slug"

    def get_queryset(self):
        return self.placements()

    def get(self, request, slug):
        placement = self.get_object(path_slug=slug)
        response = Response(PublicArticleDetailSerializer(placement).data)
        response = self.finalize_response(request, response)
        return self.check_not_modified(request, response)


@extend_schema(tags=["Public"])
class PublicRelatedArticlesView(PublicAPIMixin, PlacementQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/articles/{slug}/related/ -- same-category siblings."""

    serializer_class = PublicArticleListSerializer
    pagination_class = None
    lookup_field = "path_slug"

    def get_queryset(self):
        return self.placements()

    def get(self, request, slug):
        placement = self.get_object(path_slug=slug)
        queryset = (
            self.filtered_placements()
            .filter(article__category_id=placement.article.category_id)
            .exclude(pk=placement.pk)[:6]
        )
        return Response(PublicArticleListSerializer(queryset, many=True).data)


class PublicCategoryQuerysetMixin:
    required_scope = "read:taxonomy"

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return Category.objects.none()
        return (
            Category.objects.for_site(site)
            .filter(is_active=True)
            .annotate(
                article_count=Count(
                    "articles", filter=Q(articles__is_live=True), distinct=True
                )
            )
        )


@extend_schema(tags=["Public"])
class PublicCategoryListView(PublicAPIMixin, PublicCategoryQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/categories/ -- small, fully enumerable, unpaginated."""

    serializer_class = PublicCategorySerializer
    pagination_class = None
    filter_backends = ()

    def get(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


@extend_schema(tags=["Public"])
class PublicCategoryDetailView(PublicAPIMixin, PublicCategoryQuerysetMixin, BaseAPIView):
    """GET /api/v1/public/categories/{slug}/"""

    serializer_class = PublicCategorySerializer
    pagination_class = None
    lookup_field = "slug"

    def get(self, request, slug):
        return Response(self.get_serializer(self.get_object(slug=slug)).data)


@extend_schema(tags=["Public"])
class PublicTagListView(PublicAPIMixin, BaseAPIView):
    """GET /api/v1/public/tags/ -- unpaginated; a site's tag set is small.

    Only tags that are actually on live content: an empty tag page is a thin
    page Google will not thank you for, and linking to one from a tag cloud is
    how they get crawled.
    """

    required_scope = "read:taxonomy"
    serializer_class = PublicTagSerializer
    pagination_class = None
    filter_backends = ()

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return Tag.objects.none()
        return (
            Tag.objects.for_site(site)
            .filter(is_active=True, usage_count__gt=0)
            .order_by("-usage_count", "name")
        )

    def get(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


@extend_schema(tags=["Public"])
class PublicTagDetailView(PublicTagListView):
    """GET /api/v1/public/tags/{slug}/"""

    lookup_field = "slug"

    def get(self, request, slug):
        return Response(self.get_serializer(self.get_object(slug=slug)).data)


@extend_schema(tags=["Public"], responses=PublicSiteSerializer)
class PublicSiteView(PublicAPIMixin, APIView):
    """Site configuration and SEO defaults for the calling tenant."""

    required_scope = "read:content"

    def get(self, request):
        settings_obj = get_object_or_404(
            SiteSettings.objects.select_related("site"), site=request.site
        )
        return Response(PublicSiteSerializer(settings_obj).data)


@extend_schema(tags=["Public"], responses=RedirectRuleSerializer(many=True))
class PublicRedirectsView(PublicAPIMixin, APIView):
    """The full active redirect set for this site.

    Served wholesale rather than looked up per request: the front-end
    middleware runs on every navigation, and a database round trip there would
    tax every page view to serve a rule that applies to almost none of them.
    """

    required_scope = "read:content"

    def get(self, request):
        from apps.seo.models import Redirect

        cache_key = f"pub:{request.site.pk}:redirects"
        payload = cache.get(cache_key)
        if payload is None:
            payload = list(
                Redirect.objects.filter(site=request.site, is_active=True)
                .order_by("source_path")
                .values("source_path", "target_path", "status_code", "is_regex")
            )
            cache.set(cache_key, payload, 60)
        return Response(payload)


@extend_schema(tags=["Public"], responses=SitemapIndexSerializer)
class PublicSitemapIndexView(PublicAPIMixin, APIView):
    """Shard descriptors, for Next.js ``generateSitemaps``."""

    required_scope = "read:content"

    def get(self, request):
        from apps.seo.sitemaps import shard_index

        return Response({"shards": shard_index(request.site)})


@extend_schema(tags=["Public"], responses=SitemapEntrySerializer(many=True))
class PublicSitemapShardView(PublicAPIMixin, APIView):
    """One shard's worth of sitemap entries."""

    required_scope = "read:content"

    def get(self, request, index: int):
        from apps.seo.sitemaps import shard_entries

        return Response(shard_entries(request.site, int(index)))


@extend_schema(tags=["Public"], responses=HealthSerializer)
class PublicHealthView(APIView):
    """Unauthenticated probe so a partner can verify connectivity."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        return Response({"status": "ok"})
