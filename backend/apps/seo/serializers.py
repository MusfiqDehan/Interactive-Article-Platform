"""Studio-facing SEO serializers."""

from __future__ import annotations

from rest_framework import serializers

from .models import Redirect, SEOAnalysis, SEOMetadata


class SEOMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEOMetadata
        exclude = ("content_type", "object_id")
        read_only_fields = ("id", "updated_at")


class RedirectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Redirect
        fields = (
            "id", "source_path", "target_path", "status_code", "is_regex",
            "is_active", "hit_count", "last_hit_at", "note", "created_at",
        )
        read_only_fields = ("id", "hit_count", "last_hit_at", "created_at")

    def validate(self, attrs):
        source = Redirect._normalise(attrs.get("source_path", ""))
        target = attrs.get("target_path", "")
        if not target.startswith(("http://", "https://")):
            target = Redirect._normalise(target)

        if source == target:
            raise serializers.ValidationError(
                {"target_path": "A redirect cannot point at itself."}
            )

        # Walk the existing chain to catch loops before they reach the
        # front-end middleware, where they would become an infinite redirect.
        site = self.context.get("site")
        if site is not None and not target.startswith(("http://", "https://")):
            seen = {source}
            cursor = target
            for _ in range(5):
                nxt = (
                    Redirect.objects.filter(
                        site=site, source_path=cursor, is_active=True
                    )
                    .values_list("target_path", flat=True)
                    .first()
                )
                if nxt is None:
                    break
                if nxt in seen:
                    raise serializers.ValidationError(
                        {"target_path": f"This creates a redirect loop via {cursor}."}
                    )
                seen.add(nxt)
                cursor = nxt

        attrs["source_path"] = source
        attrs["target_path"] = target
        return attrs


class SEOAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEOAnalysis
        fields = ("score", "readability_score", "checks", "computed_at")


class SEOAnalysisSerializer(serializers.Serializer):
    """Response of `POST /api/v1/studio/articles/{slug}/analyze-seo/`."""

    score = serializers.IntegerField()
    checks = serializers.ListField(child=serializers.DictField())
    resolved_seo = serializers.DictField()
    cached = serializers.BooleanField()


class SEODraftSerializer(serializers.Serializer):
    """Optional unsaved draft to score instead of the stored article."""

    title = serializers.CharField(required=False, allow_blank=True)
    excerpt = serializers.CharField(required=False, allow_blank=True)
    content = serializers.DictField(required=False)
    featured_image = serializers.CharField(required=False, allow_blank=True)
