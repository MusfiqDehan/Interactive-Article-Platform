"""Serializers for the editorial surface."""

from __future__ import annotations

from rest_framework import serializers

from .models import AuditLogEntry, ReviewAssignment, ReviewComment, Revision
from .transitions import TRANSITIONS


class RevisionListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    #: The list view is used to render a history sidebar, so it must stay cheap.
    #: Snapshots are whole articles; sending them here would make the payload
    #: scale with revision count times article size.
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Revision
        fields = (
            "id",
            "number",
            "status",
            "content_hash",
            "created_at",
            "created_by",
            "created_by_name",
            "reason",
            "is_autosave",
            "summary",
        )

    def get_created_by_name(self, revision):
        user = revision.created_by
        if user is None:
            return "system"
        return getattr(user, "full_name", "") or user.email

    def get_summary(self, revision):
        snapshot = revision.snapshot or {}
        content = snapshot.get("content") or {}
        blocks = content.get("blocks") if isinstance(content, dict) else []
        return {
            "title": snapshot.get("title", ""),
            "blocks": len(blocks or []),
        }


class RevisionDetailSerializer(RevisionListSerializer):
    class Meta(RevisionListSerializer.Meta):
        fields = RevisionListSerializer.Meta.fields + ("snapshot",)


class AuditLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLogEntry
        fields = (
            "id",
            "action",
            "actor",
            "actor_label",
            "article",
            "target_label",
            "from_state",
            "to_state",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ReviewAssignmentSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    # An assignment that can only say "Article #12" forces the reviewer to open
    # each one to find out what it is. The list view select_relates `article`,
    # so these cost no extra query.
    article_title = serializers.CharField(source="article.title", read_only=True)
    article_slug = serializers.CharField(source="article.slug", read_only=True)

    class Meta:
        model = ReviewAssignment
        fields = (
            "id",
            "article",
            "article_title",
            "article_slug",
            "assignee",
            "assignee_name",
            "assigned_by",
            "state",
            "note",
            "created_at",
            "resolved_at",
        )
        read_only_fields = ("assigned_by", "created_at", "resolved_at")

    def get_assignee_name(self, assignment):
        user = assignment.assignee
        return getattr(user, "full_name", "") or user.email


class ReviewCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ReviewComment
        fields = (
            "id",
            "article",
            "block_id",
            "author",
            "author_name",
            "body",
            "is_resolved",
            "resolved_by",
            "created_at",
            "resolved_at",
        )
        read_only_fields = ("author", "resolved_by", "created_at", "resolved_at")

    def get_author_name(self, comment):
        user = comment.author
        if user is None:
            return "unknown"
        return getattr(user, "full_name", "") or user.email


class TransitionRequestSerializer(serializers.Serializer):
    """Body of ``POST /articles/{slug}/transition/``."""

    transition = serializers.ChoiceField(choices=sorted(TRANSITIONS))
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    #: Only meaningful for ``schedule``; validated by the transition's guard
    #: rather than here, so there is one definition of "a valid schedule time".
    scheduled_publish_at = serializers.DateTimeField(required=False, allow_null=True)


class ScheduleRequestSerializer(serializers.Serializer):
    scheduled_publish_at = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_unpublish_at = serializers.DateTimeField(required=False, allow_null=True)


class BulkTransitionRequestSerializer(serializers.Serializer):
    """Body of ``POST /articles/bulk-transition/``."""

    slugs = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    transition = serializers.ChoiceField(choices=sorted(TRANSITIONS))
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class BulkTransitionRowSerializer(serializers.Serializer):
    slug = serializers.CharField()
    ok = serializers.BooleanField()
    #: `ok` / `not_found` / `forbidden` / `illegal` -- a stable key the UI can
    #: group and style by, rather than matching on prose that may be reworded.
    code = serializers.CharField()
    detail = serializers.CharField(allow_blank=True)
    status = serializers.CharField(required=False)


class BulkTransitionResultSerializer(serializers.Serializer):
    requested = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    failed = serializers.IntegerField()
    results = BulkTransitionRowSerializer(many=True)
