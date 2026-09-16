"""Rate limiting for the public delivery API.

Throttling is per API key rather than per IP: partner sites fetch through a
single server-side origin, so an IP bucket would either be uselessly large or
would throttle a whole tenant on one busy request. Each key can also carry its
own limit via ``ApiKey.rate_limit_per_minute``.
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle

DEFAULT_API_KEY_RATE = 600  # requests per minute


class ApiKeyRateThrottle(SimpleRateThrottle):
    scope = "api_key"

    def get_cache_key(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return None  # unauthenticated requests are rejected by permissions
        return f"throttle:api_key:{api_key.pk}"

    def get_rate(self):
        # Parsed per-request in allow_request when a key overrides it.
        return f"{DEFAULT_API_KEY_RATE}/min"

    def allow_request(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is not None and api_key.rate_limit_per_minute:
            self.num_requests = api_key.rate_limit_per_minute
            self.duration = 60
            self.key = self.get_cache_key(request, view)
            if self.key is None:
                return True
            self.history = self.cache.get(self.key, [])
            self.now = self.timer()
            while self.history and self.history[-1] <= self.now - self.duration:
                self.history.pop()
            if len(self.history) >= self.num_requests:
                return self.throttle_failure()
            return self.throttle_success()
        return super().allow_request(request, view)


class EventIngestThrottle(SimpleRateThrottle):
    """Looser bucket for the analytics beacon, keyed by client IP."""

    scope = "events"

    def get_cache_key(self, request, view):
        return f"throttle:events:{self.get_ident(request)}"


class AuthRateThrottle(SimpleRateThrottle):
    """IP-keyed bucket for login, register and token refresh.

    Everything else on the API needs a credential. These three are where
    credentials are guessed, so they are the ones worth throttling hard.
    """

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class StudioRateThrottle(SimpleRateThrottle):
    """Per-user bucket for the authoring API.

    Autosave can fire several times a minute; the ceiling is sized for a busy
    desk, not a scraper walking every article on the site.
    """

    scope = "studio"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None
        return f"throttle:studio:{user.pk}"
