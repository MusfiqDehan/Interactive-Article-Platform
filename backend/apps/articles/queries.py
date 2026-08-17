"""Shared article queryset scoping for the studio and editorial surfaces.

Lives here rather than in either app's ``views.py`` so both can inherit it
without importing each other. "Which articles may this user touch" has exactly
one definition; a second copy is the one that eventually disagrees.
"""

from __future__ import annotations

from django.db.models import Count, Q

from common.permissions import is_admin

from .models import Article


class ArticleScopeMixin:
    """Tenant-scoped articles, narrowed by the caller's per-site role."""

    required_site_role = "author"
    lookup_field = "slug"

    def get_base_queryset(self):
        return (
            Article.objects.select_related("author", "category")
            .prefetch_related("placements__site")
            .annotate(placement_count=Count("placements", distinct=True))
            # Explicit ordering is required, not cosmetic: Django strips
            # Meta.ordering from aggregated (GROUP BY) queries, which would
            # leave pagination free to return the same row on two pages.
            # `-id` is the tiebreaker for rows sharing a timestamp.
            .order_by("-updated_at", "-id")
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # Authors see their own drafts plus anything already published; editors
        # and above see everything on the site.
        if not is_admin(user) and self.site_role() == "author":
            queryset = queryset.filter(Q(author=user) | Q(status="published"))
        return queryset

    def site_role(self) -> str | None:
        from apps.tenancy.models import SiteMembership

        membership = SiteMembership.objects.filter(
            site=self.site, user=self.request.user
        ).first()
        return membership.role if membership else None
