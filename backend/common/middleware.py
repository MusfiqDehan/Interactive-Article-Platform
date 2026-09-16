"""Tenant resolution.

Sets ``request.site`` (and the matching contextvar) for every request, using the
first strategy that produces a site:

1. ``X-API-Key``  -- the public delivery API. The key *is* the tenant claim.
   Accepted as a ``?api_key=`` query parameter on the analytics beacon only;
   see ``_raw_key`` for why that exception exists and why it is narrow.
2. ``X-CMS-Site`` -- the studio UI switching tenants. Validated against the
   caller's SiteMembership in the permission layer, not here; this middleware
   only resolves, it does not authorise.
3. ``Host``       -- SSR fetches from an owned site, matched against
   ``primary_domain`` and the ``SiteDomain`` aliases.
4. The default site.

Resolution is cached per host/key so the common path costs no queries.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

from common.tenancy import reset_current_site, set_current_site

_HOST_CACHE_TTL = 300
_SITE_CACHE_TTL = 300


#: The one path where a key may arrive in the query string. `sendBeacon`
#: cannot set headers, and using `fetch` instead would mean the request is
#: cancelled when the reader navigates away -- losing exactly the events at the
#: end of a session, which are the ones worth having.
_QUERY_KEY_PATHS = ("/api/v1/public/events/",)


class TenantResolutionMiddleware(MiddlewareMixin):
    @staticmethod
    def _raw_key(request):
        """The presented API key.

        A header everywhere; a query parameter on the beacon path alone. Keys
        in URLs end up in access logs and `Referer` headers, so this is
        deliberately not a general fallback -- the beacon's key is a
        write-events key scoped to one site, and the trade is worth it only
        there.
        """
        header = request.headers.get("X-API-Key")
        if header:
            return header
        if request.path in _QUERY_KEY_PATHS:
            return request.GET.get("api_key")
        return None

    def process_request(self, request):
        api_key = None
        raw_key = self._raw_key(request)
        if raw_key:
            from apps.tenancy.models import ApiKey

            api_key = ApiKey.resolve(raw_key)
            if api_key is not None:
                api_key.touch()

        request.api_key = api_key
        request.api_scopes = list(api_key.scopes or []) if api_key else []

        site = api_key.site if api_key else None
        if site is None:
            site = self._from_header(request) or self._from_host(request) or self._default()

        request.site = site
        request._tenant_token = set_current_site(site)

    def process_response(self, request, response):
        self._reset(request)
        return response

    def process_exception(self, request, exception):
        # Without this, a contextvar set during a failing request leaks into
        # whatever the worker thread handles next.
        self._reset(request)
        return None

    @staticmethod
    def _reset(request):
        token = getattr(request, "_tenant_token", None)
        if token is not None:
            reset_current_site(token)
            request._tenant_token = None

    # -- strategies ----------------------------------------------------

    @staticmethod
    def _from_header(request):
        slug = request.headers.get("X-CMS-Site")
        if not slug:
            return None
        from apps.tenancy.models import Site

        return Site.objects.filter(slug=slug, is_active=True).first()

    @staticmethod
    def _from_host(request):
        host = (request.get_host() or "").split(":")[0].lower()
        if not host:
            return None

        cache_key = f"tenancy:host:{host}"
        site_id = cache.get(cache_key)
        from apps.tenancy.models import Site, SiteDomain

        if site_id is not None:
            # Cached miss is stored as 0 so repeated unknown hosts stay cheap.
            if site_id == 0:
                return None
            site = Site.objects.filter(pk=site_id, is_active=True).first()
            if site is not None:
                return site

        site = Site.objects.filter(primary_domain=host, is_active=True).first()
        if site is None:
            domain = (
                SiteDomain.objects.select_related("site")
                .filter(domain=host, site__is_active=True)
                .first()
            )
            site = domain.site if domain else None

        cache.set(cache_key, site.pk if site else 0, _HOST_CACHE_TTL)
        return site

    @staticmethod
    def _default():
        from apps.tenancy.models import Site

        cache_key = "tenancy:default_site"
        site_id = cache.get(cache_key)
        if site_id:
            site = Site.objects.filter(pk=site_id).first()
            if site is not None:
                return site

        site = Site.get_default()
        if site is not None:
            cache.set(cache_key, site.pk, _SITE_CACHE_TTL)
        return site
