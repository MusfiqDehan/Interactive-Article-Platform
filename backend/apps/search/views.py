"""Search endpoints: public query + tenant token, studio rebuild."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasSiteRole, HasValidApiKey
from common.throttles import ApiKeyRateThrottle
from common.views import BaseAPIView

from . import client


class SearchHitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()
    path_slug = serializers.CharField()
    excerpt = serializers.CharField()
    category = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    reading_time = serializers.IntegerField()
    published_at = serializers.IntegerField()


class SearchResultSerializer(serializers.Serializer):
    query = serializers.CharField()
    hits = SearchHitSerializer(many=True)
    total = serializers.IntegerField()
    #: False when the engine is unreachable. The front end shows "search is
    #: temporarily unavailable" rather than "no results", which are very
    #: different messages to a reader.
    available = serializers.BooleanField()


class SearchTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
    host = serializers.CharField()
    index = serializers.CharField()


@extend_schema(tags=["Public"], responses=SearchResultSerializer)
class PublicSearchView(APIView):
    """GET /api/v1/public/search/?q=

    A server-side fallback. The fast path is the browser querying Meilisearch
    directly with a tenant token (see below); this exists for crawlers, no-JS
    readers, and the case where the token endpoint is unavailable.
    """

    permission_classes = (HasValidApiKey,)
    throttle_classes = (ApiKeyRateThrottle,)
    authentication_classes = ()
    required_scope = "read:content"

    def get(self, request):
        site = getattr(request, "site", None)
        query = (request.query_params.get("q") or "").strip()
        if site is None or not query:
            return Response({"query": query, "hits": [], "total": 0, "available": True})

        limit = min(int(request.query_params.get("limit") or 20), 50)
        offset = max(int(request.query_params.get("offset") or 0), 0)

        filters = []
        if category := request.query_params.get("category"):
            filters.append(f'category_slug = "{category}"')
        if tag := request.query_params.get("tag"):
            filters.append(f'tags = "{tag}"')

        result = client.search(
            site.pk, query, limit=limit, offset=offset, filters=filters
        )
        return Response(
            {
                "query": query,
                "hits": result.get("hits", []),
                "total": result.get("estimatedTotalHits", 0),
                "available": result.get("available", True),
            }
        )


@extend_schema(tags=["Public"], responses=SearchTokenSerializer)
class SearchTokenView(APIView):
    """GET /api/v1/public/search/token/

    Mints a signed, scoped token so the browser can query the search engine
    **without a Django hop**. Search is typed, so it fires per keystroke;
    proxying every one of those through the application server is the single
    place a redundant hop is most felt.

    The scope is inside the signature, so the token cannot be edited to widen
    it -- which is the only reason handing one to a browser is safe.
    """

    permission_classes = (HasValidApiKey,)
    throttle_classes = (ApiKeyRateThrottle,)
    authentication_classes = ()
    required_scope = "read:content"

    def get(self, request):
        from django.conf import settings
        from django.utils import timezone

        site = getattr(request, "site", None)
        if site is None:
            return Response({"token": "", "host": "", "index": ""})

        token = client.tenant_token(
            site.pk, expires_at=timezone.now() + timezone.timedelta(hours=6)
        )
        return Response(
            {
                "token": token,
                # The *public* host, which may differ from the internal URL the
                # backend uses to reach the engine on the container network.
                "host": getattr(settings, "MEILISEARCH_PUBLIC_URL", "")
                or getattr(settings, "MEILISEARCH_URL", ""),
                "index": client.index_name(site.pk),
            }
        )


@extend_schema(tags=["Studio"], request=None, responses=SearchResultSerializer)
class RebuildIndexView(BaseAPIView):
    """POST /api/v1/studio/search/rebuild/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = SearchResultSerializer
    pagination_class = None

    def post(self, request):
        from .tasks import rebuild_index

        rebuild_index.delay(request.site.pk)
        return Response(
            {
                "detail": "Rebuilding. The current index keeps serving until the "
                "new one is swapped in.",
                "index": client.index_name(request.site.pk),
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(tags=["Studio"], responses=SearchResultSerializer)
class SearchHealthView(BaseAPIView):
    """GET /api/v1/studio/search/health/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "editor"
    serializer_class = SearchResultSerializer
    pagination_class = None

    def get(self, request):
        from .models import IndexingLog

        engine = client.get_client()
        logs = IndexingLog.objects.for_site(request.site)
        return Response(
            {
                "available": engine is not None,
                "index": client.index_name(request.site.pk),
                "indexed": logs.filter(state="indexed").count(),
                "failed": logs.filter(state="failed").count(),
            }
        )
