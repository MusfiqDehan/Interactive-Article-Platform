import os
from datetime import timedelta
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="django-insecure-change-me-in-production-x9k2m4n6p8q0r1s3t5u7v9w",
)

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
]

LOCAL_APPS = [
    # tenancy first: other apps' migrations depend on the default Site existing.
    "apps.tenancy",
    "apps.accounts",
    "apps.categories",
    "apps.taxonomy",
    "apps.media_library",
    # Before articles: Article imports the workflow states for its field
    # choices, and the audit log holds an FK back to Article.
    "apps.editorial",
    "apps.articles",
    "apps.syndication",
    "apps.social",
    "apps.analytics",
    "apps.search",
    "apps.seo",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # After AuthenticationMiddleware: tenant resolution may need request.user
    # to validate an X-CMS-Site claim.
    "common.middleware.TenantResolutionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Deny by default. Previously IsAuthenticatedOrReadOnly, which made every
    # new viewset publicly readable unless someone remembered to say otherwise
    # -- a leak waiting to happen as studio endpoints (API key metadata, site
    # settings, deliveries) come online. Public routes now opt in explicitly.
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "api_key": "600/min",
        "events": "120/min",
    },
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Interactive Articles API",
    "DESCRIPTION": "A dynamic, interactive article system with rich content blocks, multimedia support, and interactive modal elements.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Auth", "description": "Authentication & user management"},
        {"name": "Categories", "description": "Article categories & subcategories"},
        {"name": "Articles", "description": "Article CRUD & content management"},
        {"name": "Media", "description": "Media file upload & management"},
    ],
}

# CORS
CORS_ALLOW_CREDENTIALS = True

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

# ---------------------------------------------------------------------------
# Redis: cache, Celery broker, locks
# ---------------------------------------------------------------------------
# Logical database split so a `FLUSHDB` on one concern cannot wipe another:
#   0 broker | 1 cache | 2 results | 3 locks + buffers
REDIS_URL = config("REDIS_URL", default="redis://redis:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
        "KEY_PREFIX": "ia",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # A Redis outage must degrade the site, not take it down: reads
            # fall through to the database instead of raising.
            "IGNORE_EXCEPTIONS": True,
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
        },
    }
}
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=f"{REDIS_URL}/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=f"{REDIS_URL}/2")
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = config("TIME_ZONE", default="UTC")
CELERY_ENABLE_UTC = True
# Ack after the task returns so a worker crash re-queues rather than silently
# dropping a publish. Tasks must therefore be idempotent.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Run tasks inline when there is no broker (tests, some local workflows).
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True

# Scheduled publishing sweeps. Registered in code rather than left to whoever
# remembers to add them in the django-celery-beat admin: a schedule that only
# exists in a database row is a schedule that is missing on a fresh deploy.
#
# Note that DatabaseScheduler syncs these into the DB on beat startup, so the
# entries are still editable from the admin afterwards.
CELERY_BEAT_SCHEDULE = {
    "editorial-publish-due-articles": {
        "task": "editorial.publish_due_articles",
        "schedule": 60.0,
        # If beat was down, a late tick should run once -- not queue up one task
        # per missed minute, which would stampede the workers on recovery.
        "options": {"expires": 55, "queue": "default"},
    },
    "editorial-unpublish-due-articles": {
        "task": "editorial.unpublish_due_articles",
        "schedule": 60.0,
        "options": {"expires": 55, "queue": "default"},
    },
    # Social. Once a minute is enough: `scheduled_at` is chosen to the minute
    # in the composer, so a finer sweep would only add load.
    "social-dispatch-due-posts": {
        "task": "social.dispatch_due_posts",
        "schedule": 60.0,
        "options": {"expires": 55, "queue": "default"},
    },
    "social-refresh-metrics": {
        "task": "social.refresh_metrics",
        # Hourly. Engagement numbers stop moving after a day or two, and each
        # fetch spends the platform's rate limit.
        "schedule": 3600.0,
        "options": {"expires": 3000, "queue": "default"},
    },
    # Analytics. The drain is frequent because the buffer is bounded: fall
    # far enough behind and the oldest events are trimmed away.
    "analytics-drain-events": {
        "task": "analytics.drain_events",
        "schedule": 30.0,
        "options": {"expires": 25, "queue": "default"},
    },
    "analytics-rollup-daily": {
        "task": "analytics.rollup_daily",
        "schedule": 300.0,
        "options": {"expires": 280, "queue": "default"},
    },
    "analytics-prune-events": {
        "task": "analytics.prune_events",
        "schedule": 86400.0,
        "options": {"expires": 3600, "queue": "default"},
    },
    # Search drift repair. Hourly: it exists for the case where Meilisearch was
    # down during a publish, which is measured in minutes, not seconds.
    "search-repair-drift": {
        "task": "search.repair_drift",
        "schedule": 3600.0,
        "options": {"expires": 3000, "queue": "default"},
    },
    # Delivery retries. Every 30s rather than every minute because the first
    # backoff step is 30s: a slower sweep would silently round every retry
    # interval up to the sweep period, making the schedule in common.retry a
    # fiction.
    "syndication-retry-due-deliveries": {
        "task": "syndication.retry_due_deliveries",
        "schedule": 30.0,
        "options": {"expires": 25, "queue": "default"},
    },
}

# ---------------------------------------------------------------------------
# Frontend revalidation
# ---------------------------------------------------------------------------
# Per-site values on tenancy.SiteSettings take precedence; these are the
# fallback for single-site deployments. The internal URL keeps the call on the
# container network rather than looping back out through the public domain.
FRONTEND_REVALIDATE_URL = config(
    "FRONTEND_REVALIDATE_URL", default="http://frontend:3003/api/revalidate"
)
CMS_REVALIDATE_SECRET = config("CMS_REVALIDATE_SECRET", default="")

# ---------------------------------------------------------------------------
# Object storage (S3 / R2)
# ---------------------------------------------------------------------------
# Off by default so local development keeps using the filesystem; enabling it
# only requires setting USE_S3=true plus credentials.
USE_S3 = config("USE_S3", default=False, cast=bool)

if USE_S3:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="auto")
    AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default=None)
    AWS_S3_CUSTOM_DOMAIN = config("AWS_S3_CUSTOM_DOMAIN", default=None)
    # Public objects served through a CDN: unsigned URLs are cacheable and
    # stable, which signed URLs are not.
    AWS_QUERYSTRING_AUTH = False
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "public, max-age=31536000, immutable"}

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }


# ---------------------------------------------------------------------------
# Social publishing
# ---------------------------------------------------------------------------
# Fernet key for `SocialAccount` credentials at rest. There is deliberately no
# default: falling back to plaintext would store OAuth tokens unencrypted in
# exactly the environment where nobody configured encryption.
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SOCIAL_CREDENTIAL_KEY = config("SOCIAL_CREDENTIAL_KEY", default="")

# Aggregator adapter (Phase 6). Direct per-platform adapters read the keys
# below instead; both live behind the same provider interface.
SOCIAL_AGGREGATOR_URL = config("SOCIAL_AGGREGATOR_URL", default="")
SOCIAL_AGGREGATOR_KEY = config("SOCIAL_AGGREGATOR_KEY", default="")

# Direct adapters (Phase 8). Unset means that provider reports itself
# unconfigured rather than failing at the platform with an opaque error.
LINKEDIN_CLIENT_ID = config("LINKEDIN_CLIENT_ID", default="")
LINKEDIN_CLIENT_SECRET = config("LINKEDIN_CLIENT_SECRET", default="")
X_CLIENT_ID = config("X_CLIENT_ID", default="")
X_CLIENT_SECRET = config("X_CLIENT_SECRET", default="")
META_APP_ID = config("META_APP_ID", default="")
META_APP_SECRET = config("META_APP_SECRET", default="")


# ---------------------------------------------------------------------------
# Search (Meilisearch)
# ---------------------------------------------------------------------------
# Unset means search degrades to "unavailable" everywhere rather than erroring:
# publishing, rendering and the studio all work without it.
#
# Two URLs on purpose. The backend reaches the engine over the container
# network; the browser needs a public origin, because the fast path is the
# browser querying Meilisearch directly with a tenant token.
MEILISEARCH_URL = config("MEILISEARCH_URL", default="")
MEILISEARCH_PUBLIC_URL = config("MEILISEARCH_PUBLIC_URL", default="")
MEILISEARCH_MASTER_KEY = config("MEILISEARCH_MASTER_KEY", default="")
# The *search-only* key and its uid, used to sign tenant tokens. Never the
# master key -- a tenant token derived from that would be a master key with a
# filter bolted on.
MEILISEARCH_SEARCH_KEY = config("MEILISEARCH_SEARCH_KEY", default="")
MEILISEARCH_SEARCH_KEY_UID = config("MEILISEARCH_SEARCH_KEY_UID", default="")
