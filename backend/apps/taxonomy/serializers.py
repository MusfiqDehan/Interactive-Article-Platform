from __future__ import annotations

from rest_framework import serializers

from .models import Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            "id", "name", "slug", "kind", "description",
            "usage_count", "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "usage_count", "created_at", "updated_at")
        extra_kwargs = {
            # Generated from the name when omitted, but an editor may pin it --
            # a tag slug that changes under a live URL costs a redirect.
            "slug": {"required": False, "allow_blank": True},
        }


class TagMergeSerializer(serializers.Serializer):
    """Fold one or more tags into a target.

    Takes the *sources* rather than a single pair so the studio can merge a
    whole cluster of near-duplicates in one action; doing it pairwise from the
    client would leave the taxonomy in a half-merged state if the tab closed.
    """

    into = serializers.SlugField(allow_unicode=True)
    sources = serializers.ListField(
        child=serializers.SlugField(allow_unicode=True), min_length=1, max_length=50
    )


class TagMergeResultSerializer(serializers.Serializer):
    into = TagSerializer(read_only=True)
    merged = serializers.ListField(child=serializers.CharField(), read_only=True)
    items_moved = serializers.IntegerField(read_only=True)
    skipped = serializers.ListField(child=serializers.DictField(), read_only=True)
