"""Social endpoints for the studio surface."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.articles.models import Article
from common.pagination import StudioPagination
from common.permissions import HasSiteRole
from common.views import BaseAPIView, TenantScopedAPIView

from .captions import DEFAULT_TEMPLATE, derive_for_article
from .constraints import all_specs, counted_length, spec_for
from .models import SocialAccount, SocialPost, SocialPostTarget, SocialTemplate
from .serializers import (
    CaptionPreviewRequestSerializer,
    CaptionPreviewSerializer,
    PlatformSpecSerializer,
    SocialAccountSerializer,
    SocialPostCreateSerializer,
    SocialPostSerializer,
    SocialPostTargetSerializer,
    SocialTemplateSerializer,
)


class SocialAPIView(TenantScopedAPIView):
    permission_classes = (IsAuthenticated, HasSiteRole)
    pagination_class = StudioPagination
    required_site_role = "editor"


@extend_schema(tags=["Social"], responses=PlatformSpecSerializer(many=True))
class PlatformSpecsView(BaseAPIView):
    """GET /api/v1/studio/social/platform-specs/

    The composer's counters, validators and previews are all driven from this.
    Serving the same table the server validates against is what stops the two
    ends disagreeing about whether a post fits -- the failure mode being a
    caption the editor was told was fine and the platform truncates in public.

    Not tenant-scoped and not secret: these are published platform rules.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = PlatformSpecSerializer
    pagination_class = None

    def get(self, request):
        return Response(all_specs())


class AccountQueryMixin:
    def get_base_queryset(self):
        return SocialAccount.objects.order_by("platform", "display_name")


@extend_schema(tags=["Social"])
class SocialAccountListView(AccountQueryMixin, SocialAPIView):
    """GET /api/v1/studio/social/accounts/"""

    serializer_class = SocialAccountSerializer
    filterset_fields = ("platform", "status", "provider")

    def get(self, request):
        return self.list_response(self.get_queryset())


@extend_schema(tags=["Social"])
class SocialAccountDetailView(AccountQueryMixin, SocialAPIView):
    """GET · DELETE /api/v1/studio/social/accounts/{pk}/"""

    serializer_class = SocialAccountSerializer
    pagination_class = None
    required_site_role = "owner"

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(tags=["Social"], request=None, responses=SocialAccountSerializer)
class SocialAccountConnectView(SocialAPIView):
    """POST /api/v1/studio/social/accounts/connect/

    Two steps in one endpoint, distinguished by the payload: without a
    ``callback`` it returns where to send the user; with one it completes the
    exchange. Splitting them into two routes would mean the OAuth ``state``
    round-trip had to be stored somewhere between them for no benefit.
    """

    serializer_class = SocialAccountSerializer
    pagination_class = None
    required_site_role = "owner"

    def get_base_queryset(self):
        return SocialAccount.objects.all()

    def post(self, request):
        from .providers import ProviderError, provider_for_key

        platform = request.data.get("platform")
        provider_key = request.data.get("provider", "aggregator")
        redirect_uri = request.data.get("redirect_uri", "")
        callback = request.data.get("callback")

        if not platform:
            return Response(
                {"platform": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider_cls = provider_for_key(provider_key)
        except LookupError as exc:
            return Response({"provider": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        if platform not in provider_cls.platforms:
            return Response(
                {"platform": [f"{provider_key} cannot publish to {platform}."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = provider_cls(account=None)
        try:
            if not callback:
                start = provider.begin_authorization(
                    site=request.site, platform=platform, redirect_uri=redirect_uri
                )
                return Response(
                    {"redirect_url": start.redirect_url, "state": start.state}
                )

            info = provider.complete_authorization(
                site=request.site, platform=platform, payload=callback
            )
        except ProviderError as exc:
            return Response(
                {"detail": str(exc), "code": "provider_error"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        account, _ = SocialAccount.objects.update_or_create(
            site=request.site,
            platform=platform,
            external_id=info.external_id,
            defaults={
                "provider": provider_key,
                "display_name": info.display_name,
                "handle": info.handle,
                "avatar_url": info.avatar_url,
                "status": "connected",
                "status_detail": "",
                "token_expires_at": info.expires_at,
                "connected_by": request.user,
            },
        )
        # Assigned through the property so it is encrypted; the setter is the
        # only way a credential reaches the column.
        account.credentials = info.credentials
        account.save(update_fields=["encrypted_credentials", "updated_at"])
        return Response(
            SocialAccountSerializer(account).data, status=status.HTTP_201_CREATED
        )


class TemplateQueryMixin:
    def get_base_queryset(self):
        return SocialTemplate.objects.order_by("-is_default", "name")


@extend_schema(tags=["Social"])
class SocialTemplateListView(TemplateQueryMixin, SocialAPIView):
    """GET · POST /api/v1/studio/social/templates/"""

    serializer_class = SocialTemplateSerializer

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        return self.create_object(request)


@extend_schema(tags=["Social"])
class SocialTemplateDetailView(TemplateQueryMixin, SocialAPIView):
    """GET · PATCH · DELETE /api/v1/studio/social/templates/{pk}/"""

    serializer_class = SocialTemplateSerializer
    pagination_class = None

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def patch(self, request, pk):
        return self.update_object(request, self.get_object(pk=pk))

    def delete(self, request, pk):
        return self.destroy_object(self.get_object(pk=pk))


@extend_schema(
    tags=["Social"],
    request=CaptionPreviewRequestSerializer,
    responses=CaptionPreviewSerializer(many=True),
)
class CaptionPreviewView(SocialAPIView):
    """POST /api/v1/studio/social/captions/

    Derives a per-platform caption from an article and reports, per platform,
    whether it fits. ``fits: false`` means even an empty excerpt is over the
    limit -- the caption is returned untrimmed rather than mangled, because the
    only remaining cuts would break the link or drop the title.
    """

    serializer_class = CaptionPreviewSerializer
    pagination_class = None
    required_site_role = "author"

    def get_base_queryset(self):
        return Article.objects.all()

    def post(self, request):
        payload = CaptionPreviewRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        article = None
        if data.get("article"):
            article = self.get_queryset().filter(pk=data["article"]).first()
            if article is None:
                return Response(
                    {"article": ["No such article on this site."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        platforms = data.get("platforms") or [
            account.platform
            for account in SocialAccount.objects.for_site(request.site).filter(
                status="connected"
            )
        ]
        template = data.get("template") or DEFAULT_TEMPLATE
        hashtags = data.get("hashtags") or []

        link = ""
        if article is not None:
            placement = article.placements.filter(is_primary=True).select_related("site").first()
            link = placement.url if placement else request.site.url_for(
                f"articles/{article.slug}"
            )

        results = []
        for platform in dict.fromkeys(platforms):
            if article is None:
                caption, fits = "", True
            else:
                caption, fits = derive_for_article(
                    article, platform, link=link, template=template, hashtags=hashtags
                )
            results.append(
                {
                    "platform": platform,
                    "caption": caption,
                    "fits": fits,
                    "counted_length": counted_length(caption, platform),
                    "max_length": spec_for(platform).max_length,
                }
            )
        return Response(results)


class PostQueryMixin:
    def get_base_queryset(self):
        return SocialPost.objects.prefetch_related("targets__account").order_by(
            "-created_at", "-id"
        )


@extend_schema(tags=["Social"], request=SocialPostCreateSerializer)
class SocialPostListView(PostQueryMixin, SocialAPIView):
    """GET · POST /api/v1/studio/social/posts/"""

    serializer_class = SocialPostSerializer
    filterset_fields = ("state", "article")

    def get(self, request):
        return self.list_response(self.get_queryset())

    def post(self, request):
        payload = SocialPostCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        article = None
        if data.get("article"):
            article = Article.objects.for_site(request.site).filter(
                pk=data["article"]
            ).first()
            if article is None:
                return Response(
                    {"article": ["No such article on this site."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        accounts = {
            account.pk: account
            for account in SocialAccount.objects.for_site(request.site).filter(
                pk__in=[t["account"] for t in data["targets"]]
            )
        }
        missing = [t["account"] for t in data["targets"] if t["account"] not in accounts]
        if missing:
            return Response(
                {"targets": [f"Unknown account(s): {missing}."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scheduled_at = data.get("scheduled_at")
        with transaction.atomic():
            post = SocialPost.objects.create(
                site=request.site,
                article=article,
                article_label=article.title[:300] if article else "",
                state="scheduled" if scheduled_at else "publishing",
                scheduled_at=scheduled_at,
                created_by=request.user,
            )
            target_ids = []
            for item in data["targets"]:
                account = accounts[item["account"]]
                target = SocialPostTarget.objects.create(
                    post=post,
                    account=account,
                    platform=account.platform,
                    caption=item["caption"],
                    media=item.get("media") or [],
                )
                target_ids.append(target.pk)

            if not scheduled_at:
                from .tasks import publish_target

                # on_commit: a worker that started before this transaction
                # landed would look up a target row that does not exist yet.
                transaction.on_commit(
                    lambda ids=tuple(target_ids): [
                        publish_target.delay(pk) for pk in ids
                    ]
                )

        post.refresh_from_db()
        return Response(
            SocialPostSerializer(post).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["Social"])
class SocialPostDetailView(PostQueryMixin, SocialAPIView):
    """GET · DELETE /api/v1/studio/social/posts/{pk}/"""

    serializer_class = SocialPostSerializer
    pagination_class = None

    def get(self, request, pk):
        return Response(self.get_serializer(self.get_object(pk=pk)).data)

    def delete(self, request, pk):
        post = self.get_object(pk=pk)
        if post.state == "published":
            return Response(
                {
                    "detail": "This is already live on the platforms; deleting the "
                    "record here would not remove it. Delete each target instead.",
                    "code": "already_published",
                },
                status=status.HTTP_409_CONFLICT,
            )
        post.targets.update(state="cancelled")
        post.state = "cancelled"
        post.save(update_fields=["state", "updated_at"])
        return Response(self.get_serializer(post).data)


@extend_schema(tags=["Social"], request=None, responses=SocialPostTargetSerializer)
class SocialTargetRetryView(SocialAPIView):
    """POST /api/v1/studio/social/targets/{pk}/retry/

    Per target, because a partial failure is the normal case: three platforms
    published and one did not, and re-sending the whole post would duplicate
    the three that worked.
    """

    serializer_class = SocialPostTargetSerializer
    pagination_class = None

    def get_queryset(self):
        site = getattr(self.request, "site", None)
        if site is None:
            return SocialPostTarget.objects.none()
        return SocialPostTarget.objects.filter(post__site=site).select_related(
            "account", "post"
        )

    def post(self, request, pk):
        target = self.get_object(pk=pk)
        if target.state == "published":
            return Response(
                {"detail": "Already published.", "code": "already_published"},
                status=status.HTTP_409_CONFLICT,
            )

        target.state = "pending"
        target.attempts = 0
        target.last_error = ""
        target.next_attempt_at = timezone.now()
        target.save(
            update_fields=[
                "state", "attempts", "last_error", "next_attempt_at", "updated_at",
            ]
        )

        from .tasks import publish_target

        publish_target.delay(target.pk)
        target.refresh_from_db()
        return Response(self.get_serializer(target).data)
