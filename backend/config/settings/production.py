from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# CORS
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="").split(",")

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# HSTS. Set here rather than at the proxy so it survives a proxy change, and
# `preload` is deliberately left off: getting onto the preload list is a
# one-way door for the whole apex domain, and that is a decision for whoever
# owns the domain, not a default.
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)

# The API returns JSON and is consumed cross-origin by design; a `Referer` sent
# to a partner should not leak the reader's path.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
# Tighter than development. The delivery API is fetched server-side by a small
# number of front ends, so a per-key ceiling well above normal traffic still
# catches a runaway loop; the beacon is per-IP and sized for a reader, not a
# server.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "api_key": config("THROTTLE_API_KEY", default="300/min"),
        "events": config("THROTTLE_EVENTS", default="60/min"),
        # Authentication is the one endpoint worth throttling by IP hard:
        # everything else needs a credential to reach, and this is where
        # credentials are guessed.
        "auth": config("THROTTLE_AUTH", default="20/min"),
    },
}

# Celery beat must run exactly one replica. Two beats publish every scheduled
# article twice; the `skip_locked` claim in apps.editorial.tasks is the second
# line of defence, not the first.
CELERY_BEAT_MAX_LOOP_INTERVAL = 60
