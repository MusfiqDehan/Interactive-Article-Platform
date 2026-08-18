"""Editorial endpoints.

Article-scoped views share `ArticleScopeMixin` with the studio surface, so
"which articles may this user touch" has one definition. Re-deriving it here
would produce a second copy, and the second copy is the one that ends up wrong.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.articles.queries import ArticleScopeMixin
from common.pagination import StudioPagination
from common.permissions import HasSiteRole
from common.views import TenantScopedAPIView

from .models import AuditLogEntry, ReviewAssignment, ReviewComment
from .revisions import create_revision, diff_snapshots, restore, snapshot_of
from .serializers import (
    AuditLogEntrySerializer,
    BulkTransitionRequestSerializer,
    BulkTransitionResultSerializer,
    ReviewAssignmentSerializer,
    ReviewCommentSerializer,
    RevisionDetailSerializer,
    RevisionListSerializer,
    ScheduleRequestSerializer,
    TransitionRequestSerializer,
)
from .transitions import (
    TransitionError,
    TransitionPermissionDenied,
    available,
    perform,
    record,
)


class EditorialAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination


class ArticleScopedView(ArticleScopeMixin, EditorialAPIView):
    """Base for `/studio/articles/{slug}/…` views.

    Inherits the scoping mixin rather than calling its methods with a foreign
    `self`. Borrowing an unbound method looks equivalent and is not: the
    zero-argument `super()` inside it resolves against `type(self)`'s MRO, which
    will not contain the mixin, and every request 500s on
    "obj must be an instance or subtype of type".
    """

    def article(self, slug):
        return self.get_object(slug=slug)

    def article_serializer(self, article):
        from apps.studio.serializers import StudioArticleDetailSerializer

        return StudioArticleDetailSerializer(article, context=self.get_serializer_context())


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@extend_schema(tags=["Editorial"], request=TransitionRequestSerializer)
class ArticleTransitionView(ArticleScopedView):
    """POST /api/v1/studio/articles/{slug}/transition/"""

    serializer_class = TransitionRequestSerializer

    def post(self, request, slug):
        article = self.article(slug)
        payload = TransitionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        kwargs = {}
        if data.get("scheduled_publish_at") is not None:
            kwargs["scheduled_publish_at"] = data["scheduled_publish_at"]

        try:
            perform(
                article,
                data["transition"],
                user=request.user,
                site=self.site,
                reason=data.get("reason", ""),
                **kwargs,
            )
        except TransitionPermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except TransitionError as exc:
            # 409, not 400: the request is well-formed, it just conflicts with
            # the article's current state -- which the client may not have known
            # about, and which it can resolve by refetching.
            return Response(
                {
                    "detail": str(exc),
                    "code": "illegal_transition",
                    "status": article.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if article.status == "published":
            from .tasks import after_publish

            # Deferred to commit: announcing a publish that then rolls back
            # would leave the public site ahead of the database.
            article_id = article.pk
            transaction.on_commit(lambda: after_publish.delay(article_id))

        return Response(
            {
                "article": self.article_serializer(article).data,
                "available_transitions": available(article, request.user, site=self.site),
            }
        )


@extend_schema(
    tags=["Editorial"],
    request=BulkTransitionRequestSerializer,
    responses=BulkTransitionResultSerializer,
)
class BulkTransitionView(ArticleScopeMixin, EditorialAPIView):
    """POST /api/v1/studio/articles/bulk-transition/

    **Always 200, never all-or-nothing.** Partial failure is the normal case
    here -- an editor selecting thirty articles will routinely include one that
    is already published or that they do not own. Rolling the batch back would
    punish the twenty-nine valid ones; failing fast would hide which of the
    thirty went through. Each article is attempted in its own transaction and
    reported individually, so the UI can show a per-row result.
    """

    serializer_class = BulkTransitionResultSerializer
    #: Bounded so one request cannot hold a worker for minutes. The UI batches.
    MAX_ITEMS = 100

    def post(self, request):
        payload = BulkTransitionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        slugs = payload.validated_data["slugs"]
        name = payload.validated_data["transition"]
        reason = payload.validated_data.get("reason", "")

        if len(slugs) > self.MAX_ITEMS:
            return Response(
                {"slugs": [f"At most {self.MAX_ITEMS} articles per request."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        by_slug = {a.slug: a for a in self.get_queryset().filter(slug__in=slugs)}
        results, published_ids = [], []

        for slug in slugs:
            article = by_slug.get(slug)
            if article is None:
                results.append(
                    {
                        "slug": slug,
                        "ok": False,
                        "code": "not_found",
                        "detail": "No such article, or you cannot see it.",
                    }
                )
                continue
            try:
                with transaction.atomic():
                    perform(
                        article,
                        name,
                        user=request.user,
                        site=self.site,
                        reason=reason or "bulk action",
                        metadata={"source": "bulk"},
                    )
            except TransitionPermissionDenied as exc:
                results.append(
                    {"slug": slug, "ok": False, "code": "forbidden", "detail": str(exc)}
                )
            except TransitionError as exc:
                results.append(
                    {"slug": slug, "ok": False, "code": "illegal", "detail": str(exc)}
                )
            else:
                results.append(
                    {
                        "slug": slug,
                        "ok": True,
                        "code": "ok",
                        "detail": "",
                        "status": article.status,
                    }
                )
                if article.status == "published":
                    published_ids.append(article.pk)

        if published_ids:
            from .tasks import after_publish

            def fan_out(ids=tuple(published_ids)):
                for article_id in ids:
                    after_publish.delay(article_id)

            transaction.on_commit(fan_out)

        succeeded = sum(1 for r in results if r["ok"])
        return Response(
            {
                "requested": len(slugs),
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
                "results": results,
            }
        )


@extend_schema(tags=["Editorial"])
class ArticleTransitionListView(ArticleScopedView):
    """GET /api/v1/studio/articles/{slug}/transitions/"""

    serializer_class = TransitionRequestSerializer

    def get(self, request, slug):
        article = self.article(slug)
        return Response(
            {
                "status": article.status,
                "available": available(article, request.user, site=self.site),
            }
        )


@extend_schema(tags=["Editorial"], request=ScheduleRequestSerializer)
class ArticleScheduleView(ArticleScopedView):
    """POST /api/v1/studio/articles/{slug}/schedule/

    Separate from `transition` because changing *when* an already scheduled
    article goes live is not a state change; forcing it through the state
    machine would mean an unschedule/reschedule round trip that briefly leaves
    the article unscheduled.
    """

    serializer_class = ScheduleRequestSerializer

    def post(self, request, slug):
        article = self.article(slug)
        payload = ScheduleRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        fields = []
        for field in ("scheduled_publish_at", "scheduled_unpublish_at"):
            if field in data:
                value = data[field]
                if value is not None and value <= timezone.now():
                    return Response(
                        {field: ["Must be in the future."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                setattr(article, field, value)
                fields.append(field)

        if not fields:
            return Response(
                {"detail": "Nothing to update."}, status=status.HTTP_400_BAD_REQUEST
            )

        article.save(update_fields=fields)
        record(
            site=article.site,
            action="schedule",
            user=request.user,
            article=article,
            metadata={field: str(getattr(article, field)) for field in fields},
        )
        return Response(self.article_serializer(article).data)


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------


@extend_schema(tags=["Editorial"])
class ArticleRevisionListView(ArticleScopedView):
    """GET /api/v1/studio/articles/{slug}/revisions/"""

    serializer_class = RevisionListSerializer

    def get(self, request, slug):
        article = self.article(slug)
        queryset = article.revisions.select_related("created_by").order_by("-number")
        return self.list_response(queryset, filter=False)


@extend_schema(tags=["Editorial"])
class ArticleSnapshotView(ArticleScopedView):
    """POST /api/v1/studio/articles/{slug}/snapshot/ -- a manual revision."""

    serializer_class = RevisionListSerializer

    def post(self, request, slug):
        article = self.article(slug)
        revision = create_revision(
            article,
            user=request.user,
            reason=request.data.get("reason", "manual snapshot"),
        )
        return Response(
            RevisionListSerializer(revision).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["Editorial"])
class ArticleRevisionDetailView(ArticleScopedView):
    """GET /api/v1/studio/articles/{slug}/revisions/{number}/"""

    serializer_class = RevisionDetailSerializer

    def get(self, request, slug, number):
        article = self.article(slug)
        revision = article.revisions.filter(number=number).first()
        if revision is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(RevisionDetailSerializer(revision).data)


@extend_schema(tags=["Editorial"])
class ArticleRevisionDiffView(ArticleScopedView):
    """GET /api/v1/studio/articles/{slug}/revisions/{number}/diff/

    ``?against=<n>`` compares two revisions; omitting it compares against the
    live article.
    """

    serializer_class = RevisionDetailSerializer

    def get(self, request, slug, number):
        article = self.article(slug)
        revision = article.revisions.filter(number=number).first()
        if revision is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        against = request.query_params.get("against")
        if against in (None, "", "current"):
            other_snapshot = snapshot_of(article)
            other_label = "current"
        else:
            other = article.revisions.filter(number=against).first()
            if other is None:
                return Response(
                    {"against": ["No such revision."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            other_snapshot = other.snapshot or {}
            other_label = f"v{other.number}"

        return Response(
            {
                "from": f"v{revision.number}",
                "to": other_label,
                "diff": diff_snapshots(revision.snapshot or {}, other_snapshot),
            }
        )


@extend_schema(tags=["Editorial"])
class ArticleRevisionRestoreView(ArticleScopedView):
    """POST /api/v1/studio/articles/{slug}/revisions/{number}/restore/"""

    serializer_class = RevisionDetailSerializer

    def post(self, request, slug, number):
        article = self.article(slug)
        revision = article.revisions.filter(number=number).first()
        if revision is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        restore(article, revision, user=request.user)
        article.refresh_from_db()
        return Response(self.article_serializer(article).data)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@extend_schema(tags=["Editorial"])
class ArticleAuditView(ArticleScopedView):
    """GET /api/v1/studio/articles/{slug}/audit/"""

    serializer_class = AuditLogEntrySerializer

    def get(self, request, slug):
        article = self.article(slug)
        return self.list_response(
            article.audit_entries.select_related("actor"), filter=False
        )


@extend_schema(tags=["Editorial"])
class AuditLogListView(EditorialAPIView):
    """GET /api/v1/studio/audit-log/

    Read-only by construction: there is no write handler on this class, because
    an audit log an operator can edit is not an audit log.
    """

    serializer_class = AuditLogEntrySerializer
    required_site_role = "editor"
    filterset_fields = ("action", "article", "actor")
    ordering_fields = ("created_at",)

    def get_base_queryset(self):
        return AuditLogEntry.objects.select_related("actor", "article").order_by(
            "-created_at", "-id"
        )

    def get(self, request):
        return self.list_response(self.get_queryset())


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ReviewAssignmentQueryMixin:
    required_site_role = "author"

    def get_base_queryset(self):
        return ReviewAssignment.objects.select_related(
            "article", "assignee", "assigned_by"
        ).order_by("-created_at", "-id")

    def get_queryset(self):
        queryset = super().get_queryset()
        scope = self.request.query_params.get("scope")
        user = self.request.user
        if scope == "mine":
            queryset = queryset.filter(assignee=user)
        elif scope == "requested":
            queryset = queryset.filter(assigned_by=user)
        elif scope == "open":
            queryset = queryset.filter(state="pending")
        return queryset


@extend_schema(tags=["Editorial"])
class ReviewAssignmentListView(ReviewAssignmentQueryMixin, EditorialAPIView):
    """GET · POST /api/v1/studio/reviews/"""

    serializer_class = ReviewAssignmentSerializer
    filterset_fields = ("state", "article", "assignee")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)

    def perform_create(self, serializer, **save_kwargs):
        assignment = serializer.save(
            site=self.site, assigned_by=self.request.user, **save_kwargs
        )
        record(
            site=assignment.site,
            action="review_assign",
            user=self.request.user,
            article=assignment.article,
            metadata={"assignee": assignment.assignee_id},
        )


@extend_schema(tags=["Editorial"])
class ReviewAssignmentDetailView(ReviewAssignmentQueryMixin, EditorialAPIView):
    """GET · PATCH · DELETE /api/v1/studio/reviews/{pk}/"""

    serializer_class = ReviewAssignmentSerializer

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(tags=["Editorial"])
class ReviewAssignmentResolveView(ReviewAssignmentQueryMixin, EditorialAPIView):
    """POST /api/v1/studio/reviews/{pk}/resolve/"""

    serializer_class = ReviewAssignmentSerializer

    def post(self, request, pk):
        assignment = self.get_object(pk=pk)
        state = request.data.get("state")
        if state not in ("approved", "changes_requested", "cancelled"):
            return Response(
                {"state": ["Must be approved, changes_requested or cancelled."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.state = state
        assignment.resolved_at = timezone.now()
        assignment.save(update_fields=["state", "resolved_at"])
        record(
            site=assignment.site,
            action="review_resolve",
            user=request.user,
            article=assignment.article,
            metadata={"state": state},
        )
        return Response(self.get_serializer(assignment).data)


class ReviewCommentQueryMixin:
    required_site_role = "author"

    def get_base_queryset(self):
        return ReviewComment.objects.select_related("article", "author").order_by(
            "created_at", "id"
        )


@extend_schema(tags=["Editorial"])
class ReviewCommentListView(ReviewCommentQueryMixin, EditorialAPIView):
    """GET · POST /api/v1/studio/comments/"""

    serializer_class = ReviewCommentSerializer
    filterset_fields = ("article", "is_resolved", "block_id")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)

    def perform_create(self, serializer, **save_kwargs):
        serializer.save(site=self.site, author=self.request.user, **save_kwargs)


@extend_schema(tags=["Editorial"])
class ReviewCommentDetailView(ReviewCommentQueryMixin, EditorialAPIView):
    """GET · PATCH · DELETE /api/v1/studio/comments/{pk}/"""

    serializer_class = ReviewCommentSerializer

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(tags=["Editorial"])
class ReviewCommentResolveView(ReviewCommentQueryMixin, EditorialAPIView):
    """POST /api/v1/studio/comments/{pk}/resolve/"""

    serializer_class = ReviewCommentSerializer

    def post(self, request, pk):
        comment = self.get_object(pk=pk)
        comment.is_resolved = True
        comment.resolved_by = request.user
        comment.resolved_at = timezone.now()
        comment.save(update_fields=["is_resolved", "resolved_by", "resolved_at"])
        return Response(self.get_serializer(comment).data)


@extend_schema(tags=["Editorial"])
class ReviewInboxView(EditorialAPIView):
    """GET /api/v1/studio/review-inbox/ -- articles awaiting attention."""

    required_site_role = "author"

    def get_serializer_class(self):
        from apps.studio.serializers import StudioArticleListSerializer

        return StudioArticleListSerializer

    def get_base_queryset(self):
        from apps.articles.models import Article

        return Article.objects.select_related("author", "category").order_by(
            "-updated_at", "-id"
        )

    def get_queryset(self):
        user = self.request.user
        assigned = ReviewAssignment.objects.filter(
            assignee=user, state="pending"
        ).values_list("article_id", flat=True)
        return super().get_queryset().filter(Q(status="in_review") | Q(pk__in=assigned))

    def get(self, request):
        return self.list_response(self.get_queryset())
