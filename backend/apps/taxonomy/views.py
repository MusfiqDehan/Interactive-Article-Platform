"""Tag endpoints for the studio surface."""

from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.pagination import StudioPagination
from common.permissions import HasSiteRole
from common.views import TenantScopedAPIView

from .models import Tag
from .serializers import TagMergeResultSerializer, TagMergeSerializer, TagSerializer


class TagQueryMixin:
    required_site_role = "author"
    lookup_field = "slug"
    serializer_class = TagSerializer

    def get_base_queryset(self):
        return Tag.objects.order_by("name", "id")


class TagAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination


@extend_schema(tags=["Taxonomy"])
class TagListView(TagQueryMixin, TagAPIView):
    """GET · POST /api/v1/studio/tags/"""

    filterset_fields = ("kind", "is_active")
    search_fields = ("name", "slug", "description")
    ordering_fields = ("name", "usage_count", "created_at")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        # Creating tags is part of writing an article, so authors may do it;
        # renaming and merging reshapes the whole taxonomy and is editor-only
        # (see the detail and merge views).
        return self.create_object(request)


@extend_schema(tags=["Taxonomy"])
class TagDetailView(TagQueryMixin, TagAPIView):
    """GET · PATCH · DELETE /api/v1/studio/tags/{slug}/"""

    #: Reading a tag is part of authoring. Renaming or deleting one reshapes
    #: every URL and every article that carries it, so those are editor work.
    #: Declared per method rather than mutated mid-request, so the permission
    #: class sees the right value on its own first pass.
    ROLE_BY_METHOD = {"GET": "author"}

    @property
    def required_site_role(self):
        return self.ROLE_BY_METHOD.get(getattr(self.request, "method", ""), "editor")

    def get(self, request, slug):
        return Response(self.get_serializer(self.get_object(slug=slug)).data)

    def patch(self, request, slug):
        return self.update_object(request, self.get_object(slug=slug))

    def delete(self, request, slug):
        tag = self.get_object(slug=slug)
        # Deleting a tag that is still in use silently strips it from every
        # article. Refuse and point at merge, which is what the editor
        # actually wants when a tag is "wrong" rather than "unused".
        if tag.tagged_items.exists():
            return Response(
                {
                    "detail": (
                        f"'{tag.name}' is used by {tag.tagged_items.count()} item(s). "
                        "Merge it into another tag, or remove it from those items first."
                    ),
                    "code": "tag_in_use",
                    "usage_count": tag.tagged_items.count(),
                },
                status=status.HTTP_409_CONFLICT,
            )
        return self.destroy_object(tag)


@extend_schema(
    tags=["Taxonomy"], request=TagMergeSerializer, responses=TagMergeResultSerializer
)
class TagMergeView(TagQueryMixin, TagAPIView):
    """POST /api/v1/studio/tags/merge/

    Merging is destructive and irreversible, so it is reported the way bulk
    actions are: which tags were folded in, how many items moved, and which
    were skipped and why -- rather than a bare 204 that leaves the editor to
    reload and count.
    """

    required_site_role = "editor"
    serializer_class = TagMergeSerializer

    def post(self, request):
        payload = TagMergeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        queryset = self.get_queryset()
        target = queryset.filter(slug=data["into"]).first()
        if target is None:
            return Response(
                {"into": ["No such tag on this site."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        merged, skipped, moved = [], [], 0
        with transaction.atomic():
            for slug in data["sources"]:
                if slug == target.slug:
                    skipped.append({"slug": slug, "reason": "Same as the target."})
                    continue
                source = queryset.filter(slug=slug).first()
                if source is None:
                    skipped.append({"slug": slug, "reason": "No such tag."})
                    continue
                moved += source.merge_into(target)
                merged.append(slug)

        target.refresh_from_db()
        return Response(
            {
                "into": TagSerializer(target).data,
                "merged": merged,
                "items_moved": moved,
                "skipped": skipped,
            }
        )
