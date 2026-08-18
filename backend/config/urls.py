"""Root URL map.

Two content surfaces, one auth surface, and nothing else. The legacy
``/api/articles/``, ``/api/categories/`` and ``/api/media/`` routes and the
Django admin were removed once the studio replaced them; there is no third way
to reach content, which is the point -- permissions, tenant scoping and the
editorial state machine are enforced on those two surfaces, and a bypass route
would only ever be a hole in all three.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from common.health import healthz, readyz

urlpatterns = [
    # Operational probes (see common.health for the liveness/readiness split)
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    # v1 surfaces
    path("api/v1/public/", include("apps.publicapi.urls")),
    path("api/v1/studio/", include("apps.studio.urls")),
    # Authentication. Deliberately not versioned alongside the two content
    # surfaces: both of them and the front end's login flow share it, and
    # moving it would invalidate every stored token for no benefit.
    path("api/auth/", include("apps.accounts.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
