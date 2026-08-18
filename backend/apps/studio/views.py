"""Authoring API (``/api/v1/studio/``).

JWT-authenticated and tenant-scoped. Every view extends
``TenantScopedAPIView``, whose ``get_queryset()`` is final -- a view author
cannot accidentally expose another tenant's rows, because there is no hook in
which to forget the filter.

Each class handles exactly the HTTP methods it declares. A collection view has
``get``/``post``; a detail view has ``get``/``patch``/``delete``. Anything else
405s, which is the intended answer rather than an accident of what a router
happened to generate.
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.articles.models import Article
from apps.articles.queries import ArticleScopeMixin
from apps.categories.models import Category
from apps.editorial.revisions import record_edit
from apps.editorial.transitions import record
from apps.media_library.models import MediaFile
from apps.syndication.models import Placement
from apps.taxonomy.models import TaggedItem
from apps.tenancy.models import ApiKey, Site, SiteMembership, SiteSettings
from common.cache import bump_content_version
from common.concurrency import OptimisticConcurrencyMixin
from common.pagination import StudioPagination
from common.permissions import HasSiteRole, is_admin
from common.views import BaseAPIView, TenantScopedAPIView

from .serializers import (
    StudioApiKeySerializer,
    StudioArticleDetailSerializer,
    StudioArticleListSerializer,
    StudioCategoryMoveSerializer,
    StudioCategoryNodeSerializer,
    StudioCategorySerializer,
    StudioMediaSerializer,
    StudioMembershipSerializer,
    StudioScheduleEntrySerializer,
    StudioPlacementSerializer,
    StudioSiteSerializer,
    StudioSiteSettingsSerializer,
)


class StudioAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


@extend_schema(tags=["Studio"])
class StudioArticleListView(ArticleScopeMixin, StudioAPIView):
    """GET · POST /api/v1/studio/articles/"""

    serializer_class = StudioArticleListSerializer
    search_fields = ("title", "excerpt", "plain_text")
    filterset_fields = ("status", "category", "author", "is_featured")
    ordering_fields = ("published_at", "created_at", "updated_at", "views_count", "title")

    def get_queryset(self):
        queryset = super().get_queryset()
        # `?tag=slug` (repeatable). A tag lives on a generic through-table, so
        # django-filter cannot express it declaratively; repeated values narrow
        # rather than widen, because "show me articles about both X and Y" is
        # what stacking filter chips means to the person clicking them.
        tags = [slug for slug in self.request.query_params.getlist("tag") if slug]
        if tags:
            content_type = ContentType.objects.get_for_model(Article)
            for slug in tags:
                queryset = queryset.filter(
                    pk__in=TaggedItem.objects.filter(
                        content_type=content_type, tag__slug=slug
                    ).values("object_id")
                )
        return queryset

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(
            request, serializer_class=StudioArticleDetailSerializer
        )

    def perform_create(self, serializer, **save_kwargs):
        article = serializer.save(site=self.site, author=self.request.user, **save_kwargs)
        bump_content_version(article.site_id)
        # v1 is the empty starting point, so a later "restore to original" has
        # something to restore to.
        record_edit(article, user=self.request.user, reason="created")
        record(
            site=article.site,
            action="create",
            user=self.request.user,
            article=article,
            to_state=article.status,
        )


@extend_schema(tags=["Studio"])
class StudioArticleDetailView(
    OptimisticConcurrencyMixin, ArticleScopeMixin, StudioAPIView
):
    """GET · PATCH · PUT · DELETE /api/v1/studio/articles/{slug}/

    Writes honour ``If-Match``; see ``common.concurrency``.
    """

    serializer_class = StudioArticleDetailSerializer

    def get(self, request, slug):
        article = self.get_object(slug=slug)
        return self.tag_response(Response(self.get_serializer(article).data), article)

    def patch(self, request, slug):
        return self._write(request, slug, partial=True)

    def put(self, request, slug):
        return self._write(request, slug, partial=False)

    def _write(self, request, slug, *, partial):
        article = self.get_object(slug=slug)
        conflict = self.check_precondition(article)
        if conflict is not None:
            return conflict
        response = self.update_object(request, article, partial=partial)
        article.refresh_from_db()
        return self.tag_response(response, article)

    def perform_update(self, serializer):
        article = serializer.save()
        bump_content_version(article.site_id)
        # No-ops when the content is unchanged, and coalesces rapid autosaves by
        # the same author -- see apps.editorial.revisions.record_edit.
        record_edit(article, user=self.request.user)

    def delete(self, request, slug):
        return self.destroy_object(self.get_object(slug=slug))

    def perform_destroy(self, instance):
        site_id = instance.site_id
        # Written before the delete: afterwards there is no article to name, and
        # the FK is SET_NULL, so the entry survives on its denormalised label.
        record(
            site=instance.site,
            action="delete",
            user=self.request.user,
            article=instance,
            from_state=instance.status,
            metadata={"slug": instance.slug},
        )
        instance.delete()
        bump_content_version(site_id)


@extend_schema(tags=["Studio"])
class StudioArticlePlacementsView(ArticleScopeMixin, StudioAPIView):
    """GET · POST /api/v1/studio/articles/{slug}/placements/"""

    serializer_class = StudioPlacementSerializer

    def get(self, request, slug):
        article = self.get_object(slug=slug)
        queryset = article.placements.select_related("site")
        return Response(StudioPlacementSerializer(queryset, many=True).data)

    def post(self, request, slug):
        article = self.get_object(slug=slug)
        serializer = StudioPlacementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        placement = serializer.save(article=article)
        bump_content_version(placement.site_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class StudioCategoryQueryMixin:
    required_site_role = "editor"
    lookup_field = "slug"

    def get_base_queryset(self):
        return (
            Category.objects.annotate(
                article_count=Count("articles", distinct=True),
                child_count=Count("children", distinct=True),
            )
            .order_by("depth", "order", "name", "id")
        )


@extend_schema(tags=["Studio"])
class StudioCategoryListView(StudioCategoryQueryMixin, StudioAPIView):
    """GET · POST /api/v1/studio/categories/"""

    serializer_class = StudioCategorySerializer

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)


@extend_schema(tags=["Studio"])
class StudioCategoryDetailView(StudioCategoryQueryMixin, StudioAPIView):
    """GET · PATCH · DELETE /api/v1/studio/categories/{slug}/"""

    serializer_class = StudioCategorySerializer

    def get(self, request, slug):
        return Response(self.get_serializer(self.get_object(slug=slug)).data)

    def patch(self, request, slug):
        return self.update_object(request, self.get_object(slug=slug))

    def put(self, request, slug):
        return self.update_object(request, self.get_object(slug=slug), partial=False)

    def delete(self, request, slug):
        return self.destroy_object(self.get_object(slug=slug))


@extend_schema(tags=["Studio"])
class StudioCategoryTreeView(StudioCategoryQueryMixin, StudioAPIView):
    """GET /api/v1/studio/categories/tree/ -- the whole tree, nested.

    Unpaginated and assembled in Python from a single query. Paginating a tree
    is meaningless (page 2 would be a bag of orphans), and fetching children
    per node would be one query per category on a screen whose entire job is to
    show every category at once.
    """

    serializer_class = StudioCategoryNodeSerializer
    pagination_class = None

    def get(self, request):
        nodes = list(self.get_queryset())
        children_by_parent = {}
        for node in nodes:
            children_by_parent.setdefault(node.parent_id, []).append(node)

        context = self.get_serializer_context()
        context["children_by_parent"] = children_by_parent
        roots = children_by_parent.get(None, [])
        return Response(
            StudioCategoryNodeSerializer(roots, many=True, context=context).data
        )


@extend_schema(
    tags=["Studio"],
    request=StudioCategoryMoveSerializer,
    responses=StudioCategorySerializer,
)
class StudioCategoryMoveView(StudioCategoryQueryMixin, StudioAPIView):
    """POST /api/v1/studio/categories/{slug}/move/

    Separate from PATCH because a move is not a field edit: it rewrites the
    ``url_path`` of every descendant, and the response has to tell the client
    which URLs changed so it can offer to create redirects for them.
    """

    serializer_class = StudioCategorySerializer

    def post(self, request, slug):
        category = self.get_object(slug=slug)
        payload = StudioCategoryMoveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        parent = None
        if data["parent"] is not None:
            parent = self.get_queryset().filter(pk=data["parent"]).first()
            if parent is None:
                return Response(
                    {"parent": ["No such category on this site."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Captured before the move: afterwards these rows carry the new paths,
        # and the old ones are the half of the redirect the editor needs.
        before = {c.pk: c.url_path for c in [category, *category.descendants()]}

        try:
            category.move_to(parent, order=data.get("order"))
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0], "code": "illegal_move"},
                status=status.HTTP_409_CONFLICT,
            )

        category.refresh_from_db()
        changed = [
            {"id": node.pk, "name": node.name, "from": before[node.pk], "to": node.url_path}
            for node in [category, *category.descendants()]
            if before.get(node.pk) != node.url_path
        ]
        bump_content_version(category.site_id)
        record(
            site=category.site,
            action="category_move",
            user=request.user,
            metadata={"category": category.name, "parent": parent.name if parent else None},
        )
        return Response(
            {
                "category": StudioCategorySerializer(
                    self.get_queryset().get(pk=category.pk),
                    context=self.get_serializer_context(),
                ).data,
                "changed_paths": changed,
            }
        )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


class StudioMediaQueryMixin:
    required_site_role = "author"

    def get_base_queryset(self):
        return MediaFile.objects.select_related("uploaded_by").order_by("-created_at", "-id")


@extend_schema(tags=["Studio"])
class StudioMediaListView(StudioMediaQueryMixin, StudioAPIView):
    """GET · POST /api/v1/studio/media/"""

    serializer_class = StudioMediaSerializer
    filterset_fields = ("file_type",)
    search_fields = ("title", "alt_text")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)

    def perform_create(self, serializer, **save_kwargs):
        serializer.save(site=self.site, uploaded_by=self.request.user, **save_kwargs)


@extend_schema(tags=["Studio"])
class StudioMediaDetailView(StudioMediaQueryMixin, StudioAPIView):
    """GET · PATCH · DELETE /api/v1/studio/media/{pk}/"""

    serializer_class = StudioMediaSerializer

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


# ---------------------------------------------------------------------------
# Site settings and API keys
# ---------------------------------------------------------------------------


@extend_schema(tags=["Studio"])
class StudioSiteSettingsView(BaseAPIView):
    """GET · PATCH /api/v1/studio/settings/

    A singleton per tenant, so it has no collection or detail split. It used to
    be a ViewSet whose `list()` returned one object and whose `create()` was
    really an update -- HTTP verbs standing in for operations they do not mean.
    """

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = StudioSiteSettingsSerializer
    pagination_class = None

    def _settings(self):
        obj, _ = SiteSettings.objects.get_or_create(site=self.request.site)
        return obj

    def get(self, request):
        return Response(self.get_serializer(self._settings()).data)

    def patch(self, request):
        serializer = self.get_serializer(self._settings(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        bump_content_version(request.site.pk)
        return Response(serializer.data)

    # Kept so the existing client's POST keeps working; PATCH is the correct
    # verb and what new code should use.
    def post(self, request):
        return self.patch(request)


@extend_schema(tags=["Studio"])
class StudioSiteListView(BaseAPIView):
    """GET /api/v1/studio/sites/ -- the sites this user can switch to.

    Not tenant-scoped, because its whole purpose is to answer "which tenants
    may I see?" -- the one question that cannot be asked from inside a single
    tenant. Scoping is by membership instead: a user is shown exactly the sites
    they belong to, and a global admin every active site.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = StudioSiteSerializer
    pagination_class = None

    def get_queryset(self):
        sites = Site.objects.filter(is_active=True)
        if is_admin(self.request.user):
            return sites.order_by("-is_default", "name")
        return sites.filter(memberships__user=self.request.user).order_by(
            "-is_default", "name"
        )

    def get(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


@extend_schema(tags=["Studio"])
class StudioMembershipListView(BaseAPIView):
    """GET · POST /api/v1/studio/people/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = StudioMembershipSerializer
    pagination_class = StudioPagination
    search_fields = ("user__email", "user__username", "user__first_name", "user__last_name")
    filterset_fields = ("role",)

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return SiteMembership.objects.none()
        return SiteMembership.objects.filter(site=site).select_related("user")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(site=request.site)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Studio"])
class StudioMembershipDetailView(BaseAPIView):
    """PATCH · DELETE /api/v1/studio/people/{pk}/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = StudioMembershipSerializer
    pagination_class = None

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return SiteMembership.objects.none()
        return SiteMembership.objects.filter(site=site).select_related("user")

    def _guard_last_owner(self, membership):
        """Refuse a change that would leave the site with no owner.

        Not a theoretical worry: demoting or removing yourself is the most
        natural way to hand a site over, and doing it before promoting the
        replacement locks everyone out of the settings screen that would fix
        it -- including the person who did it.
        """
        if membership.role != "owner":
            return None
        remaining = (
            self.get_queryset().filter(role="owner").exclude(pk=membership.pk).count()
        )
        if remaining:
            return None
        return Response(
            {
                "detail": "This is the site's only owner. Promote someone else first.",
                "code": "last_owner",
            },
            status=status.HTTP_409_CONFLICT,
        )

    def patch(self, request, pk):
        membership = self.get_object(pk=pk)
        if request.data.get("role") not in (None, "owner"):
            blocked = self._guard_last_owner(membership)
            if blocked is not None:
                return blocked
        serializer = self.get_serializer(membership, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        membership = self.get_object(pk=pk)
        blocked = self._guard_last_owner(membership)
        if blocked is not None:
            return blocked
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Studio"])
class StudioCalendarView(ArticleScopeMixin, StudioAPIView):
    """GET /api/v1/studio/calendar/?from=&to=

    Returns every article with a date in the window, whichever date it is --
    scheduled, unscheduling, or already published -- plus the unscheduled
    drafts the calendar shows in its side rail so an editor can drag one onto
    a day.
    """

    serializer_class = StudioScheduleEntrySerializer
    pagination_class = None
    required_site_role = "author"
    #: A month view is ~40 cells; anything beyond this is a query mistake, and
    #: an unbounded window would happily serialize the entire archive.
    MAX_ENTRIES = 500

    @staticmethod
    def _timestamp(raw: str):
        """Parse an ISO-8601 query parameter, tolerating an unencoded ``+``.

        A UTC offset is written ``+00:00``, and ``+`` in a query string decodes
        to a space -- so an unencoded timestamp arrives as ``... 00:00`` and
        ``parse_datetime`` returns None. Browsers sending ``toISOString()``
        never hit this (it ends in ``Z``), which is exactly why it would have
        surfaced only from curl or a server-side caller, as a bare 400 with no
        hint as to which of the two parameters was wrong.
        """
        raw = (raw or "").strip()
        if len(raw) > 6 and raw[-6] == " " and raw[-3] == ":":
            raw = f"{raw[:-6]}+{raw[-5:]}"
        return parse_datetime(raw)

    def get(self, request):
        start = self._timestamp(request.query_params.get("from"))
        end = self._timestamp(request.query_params.get("to"))
        if start is None or end is None:
            return Response(
                {"detail": "`from` and `to` ISO-8601 timestamps are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        if timezone.is_naive(end):
            end = timezone.make_aware(end)

        window = (
            Q(scheduled_publish_at__gte=start, scheduled_publish_at__lt=end)
            | Q(scheduled_unpublish_at__gte=start, scheduled_unpublish_at__lt=end)
            | Q(published_at__gte=start, published_at__lt=end)
        )
        entries = self.get_queryset().filter(window).select_related("author")[
            : self.MAX_ENTRIES
        ]
        unscheduled = (
            self.get_queryset()
            .filter(status__in=("draft", "approved"), scheduled_publish_at__isnull=True)
            .select_related("author")
            .order_by("-updated_at")[:50]
        )
        return Response(
            {
                "entries": StudioScheduleEntrySerializer(entries, many=True).data,
                "unscheduled": StudioScheduleEntrySerializer(unscheduled, many=True).data,
            }
        )


@extend_schema(tags=["Studio"])
class StudioApiKeyListView(BaseAPIView):
    """GET · POST /api/v1/studio/api-keys/"""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = StudioApiKeySerializer
    pagination_class = StudioPagination

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return ApiKey.objects.none()
        return ApiKey.objects.filter(site=site).order_by("-created_at", "-id")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        """Mint a key. The raw value is returned here and never again."""
        name = request.data.get("name")
        if not name:
            return Response(
                {"name": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_key, raw_key = ApiKey.generate(
            site=request.site,
            name=name,
            scopes=request.data.get("scopes"),
            created_by=request.user,
        )
        payload = StudioApiKeySerializer(api_key).data
        payload["key"] = raw_key
        payload["warning"] = "Store this key now -- it cannot be retrieved again."
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Studio"])
class StudioApiKeyDetailView(BaseAPIView):
    """DELETE /api/v1/studio/api-keys/{pk}/ -- revokes rather than deletes."""

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "owner"
    serializer_class = StudioApiKeySerializer
    pagination_class = None

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return ApiKey.objects.none()
        return ApiKey.objects.filter(site=site)

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def delete(self, request, pk):
        api_key = self.get_object(pk=pk)
        # Revoke rather than delete, so the audit trail survives.
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
