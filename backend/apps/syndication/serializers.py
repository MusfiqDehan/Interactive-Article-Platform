from __future__ import annotations

from rest_framework import serializers

from .models import ContentDelivery, Destination


class DestinationSerializer(serializers.ModelSerializer):
    target_site_name = serializers.CharField(
        source="target_site.name", default=None, read_only=True
    )
    is_deliverable = serializers.BooleanField(read_only=True)
    #: Never the secret itself. Whether one exists is all the UI needs, and it
    #: is the only thing that can be shown without turning the destinations
    #: list into a credential dump.
    has_secret = serializers.SerializerMethodField()
    # NB: the raw `secret` is *not* a field here. It is attached to the create
    # response by the view and appears nowhere else, mirroring how API keys are
    # handled -- declaring it would risk it leaking into list responses.

    class Meta:
        model = Destination
        fields = (
            "id", "name", "kind", "target_site", "target_site_name",
            "endpoint_url", "headers", "events", "is_active", "is_deliverable",
            "disabled_at", "disabled_reason", "consecutive_failures",
            "has_secret", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "disabled_at", "disabled_reason", "consecutive_failures",
            "created_at", "updated_at",
        )

    def get_has_secret(self, destination) -> bool:
        return bool(destination.secret)

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", "webhook"))
        url = attrs.get("endpoint_url", getattr(self.instance, "endpoint_url", ""))
        target = attrs.get("target_site", getattr(self.instance, "target_site", None))
        if kind == "site" and target is None:
            raise serializers.ValidationError(
                {"target_site": ["Required for a site destination."]}
            )
        if kind != "site" and not url:
            raise serializers.ValidationError(
                {"endpoint_url": ["Required unless the destination is an owned site."]}
            )
        return attrs


class ContentDeliverySerializer(serializers.ModelSerializer):
    destination_name = serializers.CharField(source="destination.name", read_only=True)
    is_retryable = serializers.BooleanField(read_only=True)

    class Meta:
        model = ContentDelivery
        fields = (
            "id", "destination", "destination_name", "article", "article_label",
            "event", "state", "attempts", "next_attempt_at", "last_error",
            "response_status", "payload_snapshot", "response_snapshot",
            "is_retryable", "event_id", "created_at", "updated_at", "delivered_at",
        )
        read_only_fields = fields
