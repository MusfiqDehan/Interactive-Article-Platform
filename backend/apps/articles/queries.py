"""Shared article queryset scoping for the studio and editorial surfaces.

Lives here rather than in either app's ``views.py`` so both can inherit it
without importing each other. "Which articles may this user touch" has exactly
one definition; a second copy is the one that eventually disagrees.
"""

from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from rest_framework.permissions import IsAuthenticated

from apps.syndication.models import Placement
from common.permissions import CanEditSiteArticle, HasSiteRole, is_admin, site_membership

from .models import Article


class ArticleScopeMixin:
    """Tenant-scoped articles, narrowed by the caller's per-site role."""

    required_site_role = "author"
    lookup_field = "slug"
    permission_classes = (IsAuthenticated, HasSiteRole, CanEditSiteArticle)

    def get_base_queryset(self):
        queryset = (
            Article.objects.select_related("author", "category")
            .annotate(placement_count=Count("placements", distinct=True))
            # Explicit ordering is required, not cosmetic: Django strips
            # Meta.ordering from aggregated (GROUP BY) queries, which would
            # leave pagination free to return the same row on two pages.
            # `-id` is the tiebreaker for rows sharing a timestamp.
            .order_by("-updated_at", "-id")
        )
        # Placements are only needed on the article detail payload. Prefetching
        # them on the list turns every page of 25 into a join the serializer
        # never reads.
        if getattr(self, "lookup_field", None) and self.kwargs.get(self.lookup_field):
            queryset = queryset.prefetch_related(
                Prefetch(
                    "placements",
                    queryset=Placement.objects.select_related("site"),
                )
            )
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # Authors see their own drafts plus anything currently live; editors
        # and above see everything on the site. ``is_live`` rather than
        # ``status="published"`` so scheduled/approved copies of other authors
        # stay hidden.
        if not is_admin(user) and self.site_role() == "author":
            queryset = queryset.filter(Q(author=user) | Q(is_live=True))
        return queryset

    def site_role(self) -> str | None:
        membership = site_membership(self.request)
        return membership.role if membership else None
