from __future__ import annotations

from rest_framework import serializers

from .constraints import PLATFORMS, counted_length, spec_for
from .models import SocialAccount, SocialPost, SocialPostTarget, SocialTemplate


class SocialAccountSerializer(serializers.ModelSerializer):
    is_usable = serializers.BooleanField(read_only=True)
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = SocialAccount
        # `encrypted_credentials` is absent by construction, not by exclusion:
        # listing fields explicitly means a future column cannot leak by being
        # added to the model.
        fields = (
            "id", "platform", "provider", "display_name", "handle", "avatar_url",
            "external_id", "status", "status_detail", "is_usable",
            "token_expires_at", "last_used_at", "capabilities", "created_at",
        )
        read_only_fields = fields

    def get_capabilities(self, account):
        from .providers import get_provider

        try:
            return get_provider(account).capabilities().__dict__
        except LookupError:
            # An account whose provider was removed from the registry should
            # read as "can do nothing", not blow up the accounts list.
            return {}


class SocialTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialTemplate
        fields = ("id", "name", "platform", "body", "hashtags", "is_default", "created_at")
        read_only_fields = ("id", "created_at")


class SocialPostTargetSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.display_name", read_only=True)
    counted_length = serializers.SerializerMethodField()
    problems = serializers.SerializerMethodField()

    class Meta:
        model = SocialPostTarget
        fields = (
            "id", "account", "account_name", "platform", "caption", "media",
            "state", "attempts", "last_error", "external_id", "external_url",
            "metrics", "metrics_fetched_at", "published_at", "next_attempt_at",
            "counted_length", "problems",
        )
        read_only_fields = (
            "id", "state", "attempts", "last_error", "external_id", "external_url",
            "metrics", "metrics_fetched_at", "published_at", "next_attempt_at",
        )

    def get_counted_length(self, target):
        # As the *platform* counts it, so the composer's counter and the
        # server's validation cannot disagree.
        return counted_length(target.caption, target.platform)

    def get_problems(self, target):
        from .providers import get_provider

        try:
            provider = get_provider(target.account)
        except LookupError:
            return []
        return provider.validate(
            platform=target.platform, caption=target.caption, media=target.media
        )


class SocialPostSerializer(serializers.ModelSerializer):
    targets = SocialPostTargetSerializer(many=True, read_only=True)

    class Meta:
        model = SocialPost
        fields = (
            "id", "article", "article_label", "state", "scheduled_at",
            "targets", "created_at", "updated_at",
        )
        read_only_fields = ("id", "state", "targets", "created_at", "updated_at")


class TargetInputSerializer(serializers.Serializer):
    account = serializers.IntegerField()
    caption = serializers.CharField(allow_blank=True)
    media = serializers.ListField(child=serializers.DictField(), required=False)


class SocialPostCreateSerializer(serializers.Serializer):
    """Composer submission: one post, one target per platform."""

    article = serializers.IntegerField(required=False, allow_null=True)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    targets = TargetInputSerializer(many=True, min_length=1)

    def validate_targets(self, value):
        seen = set()
        for target in value:
            if target["account"] in seen:
                raise serializers.ValidationError(
                    "The same account appears twice; one post per account."
                )
            seen.add(target["account"])
        return value


class PlatformSpecSerializer(serializers.Serializer):
    """Mirrors ``constraints.PlatformSpec`` for the schema.

    Exists so the endpoint appears in the OpenAPI document at all --
    drf-spectacular silently drops paths it cannot type, and this one is what
    the composer's validators are generated from.
    """

    key = serializers.ChoiceField(choices=PLATFORMS)
    label = serializers.CharField()
    max_length = serializers.IntegerField()
    url_length = serializers.IntegerField(allow_null=True)
    max_images = serializers.IntegerField()
    max_videos = serializers.IntegerField()
    max_image_bytes = serializers.IntegerField()
    max_video_bytes = serializers.IntegerField()
    image_mimes = serializers.ListField(child=serializers.CharField())
    video_mimes = serializers.ListField(child=serializers.CharField())
    aspect_ratio_range = serializers.ListField(child=serializers.FloatField())
    two_step_publish = serializers.BooleanField()
    supports_alt_text = serializers.BooleanField()
    supports_scheduling = serializers.BooleanField()
    max_hashtags = serializers.IntegerField()
    notes = serializers.ListField(child=serializers.CharField())


class CaptionPreviewRequestSerializer(serializers.Serializer):
    article = serializers.IntegerField(required=False, allow_null=True)
    platforms = serializers.ListField(
        child=serializers.ChoiceField(choices=PLATFORMS), required=False
    )
    template = serializers.CharField(required=False, allow_blank=True)
    hashtags = serializers.ListField(child=serializers.CharField(), required=False)


class CaptionPreviewSerializer(serializers.Serializer):
    platform = serializers.CharField()
    caption = serializers.CharField()
    fits = serializers.BooleanField()
    counted_length = serializers.IntegerField()
    max_length = serializers.IntegerField()
