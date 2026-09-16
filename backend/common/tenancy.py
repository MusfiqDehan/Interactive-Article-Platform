"""Tenant scoping primitives.

The safety property this module exists to provide: **no queryset over tenant
data should reach the database without a ``site_id`` predicate.** Three layers
enforce it, deliberately overlapping:

1. ``TenantModel`` gives every tenant table a ``site`` FK plus ``for_site()`` /
   ``for_request()`` helpers, so scoping is one call rather than a hand-written
   filter each time.
2. ``common.views.TenantScopedAPIView`` makes ``get_queryset()`` final --
   subclasses override ``get_base_queryset()`` and the base applies the filter.
   A view author cannot forget, because there is no hook where forgetting is
   possible.
3. ``assert_queries_scoped`` (a pytest fixture) inspects executed SQL and fails
   any query that touches a tenant table without filtering on ``site_id``.

The current site is also exposed through a ``ContextVar`` so model-layer code
can reach it. Celery tasks deliberately do *not* read it -- they take an
explicit ``site_id`` argument, because a task runs outside any request and an
inherited contextvar would silently be wrong.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar

from django.db import models

_current_site: ContextVar = ContextVar("current_site", default=None)


def get_current_site():
    """Return the site for the request in flight, or ``None``."""
    return _current_site.get()


def set_current_site(site):
    """Set the current site. Returns a token for ``reset_current_site``."""
    return _current_site.set(site)


def reset_current_site(token):
    _current_site.reset(token)


@contextlib.contextmanager
def use_site(site):
    """Temporarily bind the current site (tests, management commands)."""
    token = set_current_site(site)
    try:
        yield site
    finally:
        reset_current_site(token)


class TenantQuerySet(models.QuerySet):
    def for_site(self, site):
        if site is None:
            return self.none()
        return self.filter(site=site)

    def for_request(self, request):
        return self.for_site(getattr(request, "site", None))


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager for tenant models."""


class TenantModel(models.Model):
    """Abstract base for anything owned by exactly one site.

    ``PROTECT`` rather than ``CASCADE``: deleting a site should require
    explicitly dealing with its content, not silently destroy it.
    """

    site = models.ForeignKey(
        "tenancy.Site",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()
    # Explicit, greppable escape hatch for genuinely cross-tenant work
    # (admin dashboards, Celery tasks, data migrations).
    unscoped = models.Manager()

    class Meta:
        abstract = True


# The view-layer half of this contract now lives in `common.views` as
# `TenantScopedAPIView`, which the whole API is built on. It was a ViewSet mixin
# here until the ViewSets were removed.
