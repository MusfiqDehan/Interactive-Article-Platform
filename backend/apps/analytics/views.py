"""Event ingestion (public) and dashboards (studio)."""

from __future__ import annotations

from django.db.models import F, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.articles.models import Article
from common.pagination import StudioPagination
from common.permissions import HasSiteRole, HasValidApiKey
from common.throttles import EventIngestThrottle
from common.views import BaseAPIView, TenantScopedAPIView

from .ingest import buffer, validate
from .models import ContentEvent, DailyContentStat, session_hash
from .serializers import (
    ArticleAnalyticsSerializer,
    EventBatchSerializer,
    EventIngestResultSerializer,
    SiteAnalyticsSerializer,
    TopAnnotationSerializer,
)


@extend_schema(
    tags=["Public"], request=EventBatchSerializer, responses=EventIngestResultSerializer
)
class EventIngestView(APIView):
    """POST /api/v1/public/events/

    Answers 202 without touching the database. The body arrives via
    ``navigator.sendBeacon``, whose sender cannot read the response and cannot
    retry -- so the only useful behaviours are "accept quickly" and "drop", and
    anything that could make a reader's page slow is the wrong trade.
    """

    permission_classes = (HasValidApiKey,)
    throttle_classes = (EventIngestThrottle,)
    authentication_classes = ()
    required_scope = "write:events"

    #: One beacon carries a page's worth of interactions, not a session's.
    MAX_EVENTS = 50

    def post(self, request):
        site = getattr(request, "site", None)
        if site is None:
            return Response(status=status.HTTP_202_ACCEPTED)

        payload = request.data
        raw_events = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(raw_events, list):
            raw_events = [payload] if isinstance(payload, dict) else []

        events = [
            validated
            for item in raw_events[: self.MAX_EVENTS]
            if isinstance(item, dict) and (validated := validate(item))
        ]

        session = session_hash(
            _client_ip(request), request.headers.get("User-Agent", "")
        )
        accepted = buffer(site.pk, session, events)

        # 202, always. A rejected event is not something the caller can act on,
        # and a 4xx here would show up as a console error on a reader's page.
        return Response(
            {"accepted": accepted, "received": len(raw_events)},
            status=status.HTTP_202_ACCEPTED,
        )


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # Left-most is the client; the rest are proxies we added.
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AnalyticsAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "author"
    pagination_class = StudioPagination


@extend_schema(tags=["Analytics"], responses=SiteAnalyticsSerializer)
class SiteAnalyticsView(AnalyticsAPIView):
    """GET /api/v1/studio/analytics/?days=30"""

    serializer_class = SiteAnalyticsSerializer
    pagination_class = None

    def get_base_queryset(self):
        return DailyContentStat.objects.all()

    def get(self, request):
        days = min(int(request.query_params.get("days") or 30), 365)
        start = timezone.now().date() - timezone.timedelta(days=days)
        rows = self.get_queryset().filter(day__gte=start)

        totals = rows.aggregate(
            views=Sum("views"),
            unique_sessions=Sum("unique_sessions"),
            reads_completed=Sum("reads_completed"),
            annotation_opens=Sum("annotation_opens"),
            hotspot_opens=Sum("hotspot_opens"),
            media_plays=Sum("media_plays"),
            outbound_clicks=Sum("outbound_clicks"),
            shares=Sum("shares"),
        )
        totals = {key: value or 0 for key, value in totals.items()}

        series = list(
            rows.values("day")
            .annotate(
                views=Sum("views"),
                annotation_opens=Sum("annotation_opens"),
                reads_completed=Sum("reads_completed"),
            )
            .order_by("day")
        )

        top = list(
            rows.filter(article__isnull=False)
            .values("article_id", title=F("article__title"), slug=F("article__slug"))
            .annotate(
                views=Sum("views"),
                annotation_opens=Sum("annotation_opens"),
            )
            .order_by("-views")[:10]
        )
        for row in top:
            row["interaction_rate"] = (
                round((row["annotation_opens"] or 0) / row["views"], 4)
                if row["views"]
                else 0.0
            )

        return Response(
            {
                "days": days,
                "totals": totals,
                # The headline number. Views alone say the article was served;
                # this says the interactive format was actually used.
                "interaction_rate": (
                    round(totals["annotation_opens"] / totals["views"], 4)
                    if totals["views"]
                    else 0.0
                ),
                "completion_rate": (
                    round(totals["reads_completed"] / totals["views"], 4)
                    if totals["views"]
                    else 0.0
                ),
                "series": series,
                "top_articles": top,
            }
        )


@extend_schema(tags=["Analytics"], responses=ArticleAnalyticsSerializer)
class ArticleAnalyticsView(AnalyticsAPIView):
    """GET /api/v1/studio/analytics/articles/{slug}/"""

    serializer_class = ArticleAnalyticsSerializer
    pagination_class = None
    lookup_field = "slug"

    def get_base_queryset(self):
        return Article.objects.all()

    def get(self, request, slug):
        article = self.get_object(slug=slug)
        days = min(int(request.query_params.get("days") or 30), 365)
        start = timezone.now().date() - timezone.timedelta(days=days)

        stats = DailyContentStat.objects.for_site(request.site).filter(
            article=article, day__gte=start
        )
        totals = {
            key: value or 0
            for key, value in stats.aggregate(
                views=Sum("views"),
                unique_sessions=Sum("unique_sessions"),
                reads_completed=Sum("reads_completed"),
                annotation_opens=Sum("annotation_opens"),
                hotspot_opens=Sum("hotspot_opens"),
                media_plays=Sum("media_plays"),
                outbound_clicks=Sum("outbound_clicks"),
                shares=Sum("shares"),
            ).items()
        }

        # Which annotations people actually open. The direct justification for
        # the interactive format, and unavailable from any generic analytics
        # tool -- they see one page view and nothing inside it.
        top_annotations = list(
            ContentEvent.objects.for_site(request.site)
            .filter(article=article, name="annotation_open", occurred_at__date__gte=start)
            .exclude(target_id="")
            .values("target_id")
            .annotate(opens=Sum(1))
            .order_by("-opens")[:10]
        )

        return Response(
            {
                "article": {"id": article.pk, "title": article.title, "slug": article.slug},
                "days": days,
                "totals": totals,
                "interaction_rate": (
                    round(totals["annotation_opens"] / totals["views"], 4)
                    if totals["views"]
                    else 0.0
                ),
                "series": list(
                    stats.values(
                        "day", "views", "annotation_opens", "reads_completed"
                    ).order_by("day")
                ),
                "top_annotations": [
                    {"target_id": row["target_id"], "opens": row["opens"]}
                    for row in top_annotations
                ],
            }
        )


@extend_schema(tags=["Analytics"], responses=TopAnnotationSerializer(many=True))
class BufferHealthView(BaseAPIView):
    """GET /api/v1/studio/analytics/buffer/ -- how far behind the drain is."""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = TopAnnotationSerializer
    pagination_class = None

    def get(self, request):
        from .ingest import buffered_count

        pending = buffered_count()
        return Response(
            {
                "buffered": pending,
                # A buffer that never empties means the drain is not keeping up
                # and events are about to be trimmed away.
                "healthy": pending < 50_000,
            }
        )
