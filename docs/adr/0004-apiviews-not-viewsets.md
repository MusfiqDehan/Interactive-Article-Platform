# 4. Plain APIViews with explicit URLs, not routers

**Status:** Accepted · **Phase:** 4

## Context

The API began as DRF `ModelViewSet`s behind routers. As the surface grew past
about forty endpoints, "what serves this URL?" stopped being answerable by
reading the URL files.

## Decision

Every endpoint is a plain `APIView` with explicit method handlers, wired to an
explicit `path()`. No routers anywhere. `common/views.py` supplies the
list/detail plumbing as helpers a view *calls*, not behaviour it inherits.

## Why

A router turns one `register()` into a dozen URLs nobody wrote:

```
api/articles/^featured\.(?P<format>[a-z0-9]+)/?$
```

That is a real route from the previous version. Before: 75 routes, most of them
invented, including a `.format` twin of every path. After: 68 routes you can
read top to bottom. Only four disappeared, all router artifacts — two
browsable-API roots and two detail routes generated for read-only viewsets that
nothing referenced.

Two things the conversion surfaced that the router had been hiding:

1. **Eight endpoints were missing from the OpenAPI schema entirely.**
   drf-spectacular logs "unable to guess serializer" and then *silently drops
   the path*, so a generated client would never have known they existed.
2. **Ordering constraints became visible.** `articles/featured/` must precede
   `articles/<str:slug>/`. That was always true; the router just sorted it out
   internally, so nobody knew it was load-bearing until it was written down.

## Consequences

- Each class handles exactly the methods it declares. Anything else 405s
  because someone decided so.
- More lines in `urls.py`. That is the point: the URL map is now exhaustive and
  readable, and the lines are the documentation.
- `get_object()` runs object-level permissions. A view that fetches a row
  without it silently drops its own authorisation — noted in the docstring
  because it is the one footgun the helper layer reintroduces.
