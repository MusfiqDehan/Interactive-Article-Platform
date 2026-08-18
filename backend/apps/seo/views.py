"""Studio SEO endpoints: metadata editing, redirects, and live analysis."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.articles.models import Article
from common.pagination import StudioPagination
from common.permissions import HasSiteRole
from common.views import TenantScopedAPIView

from .checks import analyze_article
from .models import Redirect, SEOMetadata
from .serializers import (
    RedirectSerializer,
    SEOAnalysisSerializer,
    SEODraftSerializer,
    SEOMetadataSerializer,
)


class RedirectQueryMixin:
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination
    serializer_class = RedirectSerializer
    required_site_role = "editor"

    def get_base_queryset(self):
        return Redirect.objects.order_by("source_path", "id")

    def get_serializer_context(self):
        # The loop check needs the tenant to walk the existing chain.
        return {**super().get_serializer_context(), "site": self.site}


@extend_schema(tags=["Studio SEO"])
class RedirectListView(RedirectQueryMixin, TenantScopedAPIView):
    """GET · POST /api/v1/studio/redirects/"""

    search_fields = ("source_path", "target_path", "note")
    filterset_fields = ("status_code", "is_active", "is_regex")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)

    def perform_create(self, serializer, **save_kwargs):
        serializer.save(site=self.site, created_by=self.request.user, **save_kwargs)


@extend_schema(tags=["Studio SEO"])
class RedirectDetailView(RedirectQueryMixin, TenantScopedAPIView):
    """GET · PATCH · DELETE /api/v1/studio/redirects/{pk}/"""

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def put(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk), partial=False)

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(
    tags=["Studio SEO"],
    request=SEOMetadataSerializer,
    responses=SEOMetadataSerializer,
)
class ArticleSEOView(APIView):
    """Read or write the SEO metadata attached to one article.

    ``?site=<slug>`` targets a per-site override; omitting it edits the default
    row that applies everywhere the article is placed.
    """

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "author"

    def _article(self, slug):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(
            Article.objects.for_request(self.request), slug=slug
        )

    def _target_site(self, request):
        scope = request.query_params.get("site")
        if not scope:
            return None  # the default (all-sites) row
        from apps.tenancy.models import Site

        return Site.objects.filter(slug=scope).first()

    def get(self, request, slug):
        article = self._article(slug)
        row = SEOMetadata.objects.filter(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=article.pk,
            site=self._target_site(request),
        ).first()
        return Response(
            {
                "stored": SEOMetadataSerializer(row).data if row else None,
                # What the front-end will actually emit, after fallbacks.
                "resolved": article.resolved_seo(site=request.site).as_dict(),
            }
        )

    def put(self, request, slug):
        article = self._article(slug)
        row, _ = SEOMetadata.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=article.pk,
            site=self._target_site(request),
        )
        serializer = SEOMetadataSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from common.cache import bump_content_version

        bump_content_version(article.site_id)
        return Response(serializer.data)


@extend_schema(
    tags=["Studio SEO"],
    request=SEODraftSerializer,
    responses=SEOAnalysisSerializer,
)
class AnalyzeSEOView(APIView):
    """Score an article, optionally against unsaved draft content.

    POSTing ``content``/``title``/``excerpt`` scores the draft the author is
    looking at rather than the last saved revision, which is what makes the
    editor's live sidebar trustworthy.
    """

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "author"

    def post(self, request, slug):
        from django.shortcuts import get_object_or_404

        article = get_object_or_404(
            Article.objects.for_request(request), slug=slug
        )

        draft = request.data or {}
        persist = True
        for field in ("title", "excerpt", "content", "featured_image"):
            if field in draft:
                setattr(article, field, draft[field])
                persist = False  # never cache a score for unsaved content

        if not persist:
            # Recompute derived text so the checks see the draft, not the DB.
            from common.blocks import blocks_to_plaintext

            article.plain_text = blocks_to_plaintext(article.content)

        score, checks, seo = analyze_article(
            article, site=request.site, persist=persist
        )
        return Response(
            {
                "score": score,
                "checks": checks,
                "resolved_seo": seo.as_dict(),
                "cached": persist,
            },
            status=status.HTTP_200_OK,
        )
