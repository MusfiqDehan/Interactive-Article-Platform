"""APIView foundations.

Every endpoint in this project is a plain ``APIView`` with explicit HTTP method
handlers, wired to an explicit ``path()``. There are no routers.

**Why not ViewSets.** A router turns one ``register()`` call into a dozen URLs
you never wrote and cannot read: list, detail, every ``@action``, and a
``.format`` twin of each. Answering "what serves this URL?" meant mentally
replaying the router's naming rules, and changing one route's path or method set
meant fighting conventions instead of editing a line. The URL map is now the
thing you read, and it is exhaustive.

What that costs is the free list/detail plumbing, which is what this module
gives back -- but as helpers a view *calls*, not behaviour it inherits and has
to override. The filtering, pagination and object-lookup semantics are identical
to DRF's generics, because they delegate to the same components.
"""

from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView


class BaseAPIView(APIView):
    """APIView plus the list/detail helpers a ViewSet used to supply.

    Subclasses declare `serializer_class` and (usually) `get_queryset()`, then
    write `get`/`post`/`patch`/`delete` explicitly. Nothing is routed by naming
    convention: a method exists on the class or the URL 405s.
    """

    serializer_class = None
    #: None disables pagination for this view; unset falls back to the DRF default.
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    filter_backends = api_settings.DEFAULT_FILTER_BACKENDS
    #: Consumed by the filter backends above, exactly as on a ViewSet.
    search_fields = ()
    filterset_fields = ()
    ordering_fields = ()
    ordering = None
    lookup_field = "pk"

    # -- serializers --------------------------------------------------------

    def get_serializer_class(self):
        assert self.serializer_class is not None, (
            f"{type(self).__name__} must set `serializer_class` or override "
            "`get_serializer_class()`."
        )
        return self.serializer_class

    def get_serializer_context(self):
        return {"request": self.request, "view": self, "format": self.format_kwarg}

    def get_serializer(self, *args, **kwargs):
        serializer_class = kwargs.pop("serializer_class", None) or self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    # -- querysets ----------------------------------------------------------

    def get_queryset(self):
        raise NotImplementedError(
            f"{type(self).__name__} must implement `get_queryset()`."
        )

    def filter_queryset(self, queryset):
        for backend in self.filter_backends:
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset

    # -- pagination ---------------------------------------------------------

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class() if self.pagination_class else None
        return self._paginator

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)

    def list_response(self, queryset, *, serializer_class=None, filter=True):
        """Filter, paginate and serialize -- the old `list()` in one call."""
        if filter:
            queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, serializer_class=serializer_class
            )
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(
            queryset, many=True, serializer_class=serializer_class
        )
        return Response(serializer.data)

    # -- objects ------------------------------------------------------------

    def get_object(self, queryset=None, **lookup):
        """Fetch one object and run object-level permissions.

        The permission check is not optional politeness: `IsAuthorOrReadOnly`
        and `IsOwnerOrAdmin` only ever act here, so a view that fetches a row
        without calling this silently drops its own authorisation.
        """
        queryset = self.get_queryset() if queryset is None else queryset
        if not lookup:
            lookup = {self.lookup_field: self.kwargs[self.lookup_field]}
        try:
            obj = queryset.get(**lookup)
        except queryset.model.DoesNotExist:
            raise Http404(f"No {queryset.model.__name__} matches the given query.")
        self.check_object_permissions(self.request, obj)
        return obj

    # -- write helpers ------------------------------------------------------

    def create_object(self, request, *, serializer_class=None, **save_kwargs):
        serializer = self.get_serializer(
            data=request.data, serializer_class=serializer_class
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer, **save_kwargs)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update_object(self, request, instance, *, partial=True, serializer_class=None):
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            serializer_class=serializer_class,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy_object(self, instance):
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Overridable side-effect hooks, kept for the same reason DRF has them:
    # they are where tenant stamping and audit entries belong.
    def perform_create(self, serializer, **save_kwargs):
        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class TenantScopedAPIView(BaseAPIView):
    """A view whose queryset is always filtered to the request's tenant.

    `get_queryset()` is final; subclasses override `get_base_queryset()`. That
    inversion is the point -- there is no hook in which a view author can forget
    the `site` filter, because the filter is not theirs to write.
    """

    def get_base_queryset(self):
        raise NotImplementedError(
            f"{type(self).__name__} must implement `get_base_queryset()`."
        )

    @property
    def site(self):
        return getattr(self.request, "site", None)

    def get_queryset(self):
        queryset = self.get_base_queryset()
        if self.site is None:
            return queryset.none()
        return queryset.filter(site=self.site)

    def perform_create(self, serializer, **save_kwargs):
        save_kwargs.setdefault("site", self.site)
        serializer.save(**save_kwargs)


def require_site(request):
    """Reject a request that resolved to no tenant, rather than 500ing later."""
    site = getattr(request, "site", None)
    if site is None:
        raise PermissionDenied("No site could be resolved for this request.")
    return site
