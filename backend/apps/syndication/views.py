"""Distribution endpoints for the studio surface."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.pagination import StudioPagination
from common.permissions import HasSiteRole
from common.views import BaseAPIView, TenantScopedAPIView

from .models import ContentDelivery, Destination
from .serializers import ContentDeliverySerializer, DestinationSerializer


class SyndicationAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination
    required_site_role = "owner"


class DestinationQueryMixin:
    def get_base_queryset(self):
        return Destination.objects.select_related("target_site").order_by("name", "id")


@extend_schema(tags=["Distribution"])
class DestinationListView(DestinationQueryMixin, SyndicationAPIView):
    """GET · POST /api/v1/studio/destinations/"""

    serializer_class = DestinationSerializer
    filterset_fields = ("kind", "is_active")
    search_fields = ("name", "endpoint_url")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        destination = serializer.save(site=request.site)
        payload = self.get_serializer(destination).data
        # The generated signing secret, shown once. The receiver needs it to
        # verify our signature, and after this response it is unreachable.
        payload["secret"] = destination.secret
        payload["warning"] = (
            "Copy this secret into the receiving system now -- it is not shown again."
        )
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Distribution"])
class DestinationDetailView(DestinationQueryMixin, SyndicationAPIView):
    """GET · PATCH · DELETE /api/v1/studio/destinations/{pk}/"""

    serializer_class = DestinationSerializer
    pagination_class = None

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(tags=["Distribution"], request=None, responses=DestinationSerializer)
class DestinationEnableView(DestinationQueryMixin, SyndicationAPIView):
    """POST /api/v1/studio/destinations/{pk}/enable/

    Re-enables a destination the failure counter switched off. A separate
    action rather than ``PATCH {"is_active": true}`` because two different
    things have to be undone -- the flag *and* the ``disabled_at`` stamp -- and
    a partial re-enable leaves a destination that reads as active and delivers
    nothing.
    """

    serializer_class = DestinationSerializer
    pagination_class = None

    def post(self, request, pk):
        destination = self.get_object(pk=pk)
        destination.is_active = True
        destination.disabled_at = None
        destination.disabled_reason = ""
        destination.consecutive_failures = 0
        destination.save(
            update_fields=[
                "is_active", "disabled_at", "disabled_reason",
                "consecutive_failures", "updated_at",
            ]
        )
        return Response(self.get_serializer(destination).data)


class DeliveryQueryMixin:
    required_site_role = "editor"

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return ContentDelivery.objects.none()
        # Scoped through the destination: ContentDelivery has no site column of
        # its own, because a delivery is always about exactly one destination
        # and duplicating the tenant there would be a second thing to keep true.
        return ContentDelivery.objects.filter(
            destination__site=site
        ).select_related("destination")


@extend_schema(tags=["Distribution"])
class DeliveryListView(DeliveryQueryMixin, BaseAPIView):
    """GET /api/v1/studio/deliveries/ -- read-only by construction."""

    permission_classes = (IsAuthenticated, HasSiteRole)
    serializer_class = ContentDeliverySerializer
    pagination_class = StudioPagination
    filterset_fields = ("state", "event", "destination", "article")
    ordering_fields = ("created_at", "delivered_at", "attempts")
    search_fields = ("article_label", "last_error")

    def get(self, request):
        return self.list_response(self.get_queryset())


@extend_schema(tags=["Distribution"])
class DeliveryDetailView(DeliveryQueryMixin, BaseAPIView):
    """GET /api/v1/studio/deliveries/{pk}/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    serializer_class = ContentDeliverySerializer
    pagination_class = None

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)


@extend_schema(
    tags=["Distribution"], request=None, responses=ContentDeliverySerializer
)
class DeliveryRetryView(DeliveryQueryMixin, BaseAPIView):
    """POST /api/v1/studio/deliveries/{pk}/retry/

    Resets the backoff and dispatches immediately. Allowed even on an abandoned
    delivery: "I fixed the receiver, try again now" is the whole reason an
    operator is looking at this screen, and making them wait out a schedule
    they know is irrelevant would just mean recreating the row by hand.
    """

    permission_classes = (IsAuthenticated, HasSiteRole)
    serializer_class = ContentDeliverySerializer
    pagination_class = None

    def post(self, request, pk):
        delivery = self.get_object(pk=pk)
        if delivery.state == "delivered":
            return Response(
                {
                    "detail": "This was already delivered successfully.",
                    "code": "already_delivered",
                },
                status=status.HTTP_409_CONFLICT,
            )
        if not delivery.destination.is_deliverable:
            return Response(
                {
                    "detail": "Re-enable the destination before retrying.",
                    "code": "destination_disabled",
                },
                status=status.HTTP_409_CONFLICT,
            )

        delivery.state = "pending"
        delivery.attempts = 0
        delivery.next_attempt_at = timezone.now()
        delivery.last_error = ""
        delivery.save(
            update_fields=[
                "state", "attempts", "next_attempt_at", "last_error", "updated_at",
            ]
        )

        from .tasks import deliver_content

        deliver_content.delay(delivery.pk)
        delivery.refresh_from_db()
        return Response(self.get_serializer(delivery).data)
