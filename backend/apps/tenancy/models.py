"""Tenant models: sites, their settings, API keys, and per-site membership.

Named ``tenancy`` rather than ``sites`` on purpose -- ``django.contrib.sites``
owns the ``sites`` app label, and a collision is an unrecoverable boot error
the moment anything pulls that app in.

A ``Site`` is a publishing destination. Content is *owned* by one site and
*placed* on any number of sites via ``syndication.Placement``.
"""

from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

API_KEY_PREFIX_LENGTH = 12


class Site(models.Model):
    KIND_CHOICES = (
        ("owned", "Owned"),
        ("partner", "Partner"),
        ("internal", "Internal"),
    )

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="owned")
    primary_domain = models.CharField(max_length=253, unique=True)
    base_url = models.URLField(help_text="Absolute origin, e.g. https://example.com")
    locale = models.CharField(max_length=10, default="en", help_text="BCP-47 tag")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tenancy"
        ordering = ["name"]
        constraints = [
            # Partial unique index: at most one default site, but any number of
            # non-default ones.
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True),
                name="tenancy_single_default_site",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Normalise so lookups by Host header match reliably.
        self.primary_domain = (self.primary_domain or "").strip().lower()
        self.base_url = (self.base_url or "").rstrip("/")
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first()

    def url_for(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"


class SiteDomain(models.Model):
    """Additional hostnames (aliases, staging domains) pointing at a site."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(max_length=253, unique=True)
    is_canonical = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tenancy"
        ordering = ["domain"]

    def __str__(self):
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = (self.domain or "").strip().lower()
        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    """Per-site configuration and SEO defaults.

    Lives here rather than in a separate settings app because every value is
    inherently tenant-scoped.
    """

    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="settings")

    site_title = models.CharField(max_length=200, blank=True, default="")
    title_template = models.CharField(
        max_length=200,
        default="%s | {site_title}",
        help_text="Next.js title template; %s is the page title.",
    )
    default_meta_description = models.TextField(max_length=320, blank=True, default="")
    default_og_image = models.URLField(max_length=500, blank=True, default="")
    organization_jsonld = models.JSONField(default=dict, blank=True)
    robots_extra = models.TextField(blank=True, default="")
    google_site_verification = models.CharField(max_length=120, blank=True, default="")
    allow_ai_crawlers = models.BooleanField(default=True)

    # On-demand revalidation target for this site's Next.js deployment.
    revalidate_url = models.URLField(max_length=500, blank=True, default="")
    revalidate_secret = models.CharField(max_length=128, blank=True, default="")

    analytics_snippet = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tenancy"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return f"Settings for {self.site.name}"


class ApiKeyQuerySet(models.QuerySet):
    def usable(self):
        now = timezone.now()
        return self.filter(revoked_at__isnull=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )


class ApiKey(models.Model):
    """Credential for the public delivery API.

    Only a hash is stored. The raw key is shown once, at creation time.
    """

    SCOPE_CHOICES = (
        ("read:content", "Read content"),
        ("read:media", "Read media"),
        ("read:taxonomy", "Read taxonomy"),
        ("write:events", "Write analytics events"),
    )

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=API_KEY_PREFIX_LENGTH, unique=True, db_index=True)
    hashed_key = models.CharField(max_length=64)
    scopes = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Requests per minute for this key; null falls back to the global default.
    rate_limit_per_minute = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_api_keys",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ApiKeyQuerySet.as_manager()

    class Meta:
        app_label = "tenancy"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"

    # -- key lifecycle -------------------------------------------------

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def generate(cls, site, name, scopes=None, **kwargs) -> tuple["ApiKey", str]:
        """Create a key and return ``(instance, raw_key)``.

        The raw key is never persisted and cannot be recovered afterwards.
        """
        raw_key = f"ia_live_{secrets.token_urlsafe(32)}"
        instance = cls.objects.create(
            site=site,
            name=name,
            prefix=raw_key[:API_KEY_PREFIX_LENGTH],
            hashed_key=cls.hash_key(raw_key),
            scopes=scopes if scopes is not None else ["read:content", "read:taxonomy"],
            **kwargs,
        )
        return instance, raw_key

    @classmethod
    def install(cls, site, raw_key: str, name="Default delivery", scopes=None, **kwargs) -> "ApiKey":
        """Persist a caller-supplied raw key. Idempotent on prefix.

        Used to wire ``CMS_SITE_API_KEY`` from the environment into the default
        site so the public delivery API works on a fresh install. The raw value
        is hashed the same way as ``generate``; only the hash is stored.
        """
        if not raw_key or len(raw_key) <= API_KEY_PREFIX_LENGTH:
            raise ValueError("raw_key is too short to install")
        prefix = raw_key[:API_KEY_PREFIX_LENGTH]
        existing = cls.objects.filter(prefix=prefix).first()
        if existing is not None:
            return existing
        return cls.objects.create(
            site=site,
            name=name,
            prefix=prefix,
            hashed_key=cls.hash_key(raw_key),
            scopes=scopes
            if scopes is not None
            else ["read:content", "read:taxonomy", "read:media", "write:events"],
            **kwargs,
        )

    @classmethod
    def resolve(cls, raw_key: str) -> "ApiKey | None":
        """Look up a usable key by its raw value, in constant time per candidate."""
        if not raw_key or len(raw_key) <= API_KEY_PREFIX_LENGTH:
            return None
        candidate = (
            cls.objects.usable()
            .select_related("site")
            .filter(prefix=raw_key[:API_KEY_PREFIX_LENGTH])
            .first()
        )
        if candidate is None:
            return None
        if not secrets.compare_digest(candidate.hashed_key, cls.hash_key(raw_key)):
            return None
        if not candidate.site.is_active:
            return None
        return candidate

    @property
    def is_usable(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def touch(self):
        """Record usage without racing other requests on the same key."""
        now = timezone.now()
        # Coarse granularity: skip the write if we already recorded a use this
        # minute, so a busy key does not generate an UPDATE per request.
        if self.last_used_at and (now - self.last_used_at).total_seconds() < 60:
            return
        type(self).objects.filter(pk=self.pk).update(last_used_at=now)
        self.last_used_at = now


class SiteMembership(models.Model):
    """Per-site role. Distinct from ``User.role``, which is global."""

    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("editor", "Editor"),
        ("author", "Author"),
        ("viewer", "Viewer"),
    )

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="site_memberships"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="viewer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tenancy"
        unique_together = ("site", "user")
        ordering = ["site__name", "user__email"]

    def __str__(self):
        return f"{self.user} @ {self.site} ({self.role})"
