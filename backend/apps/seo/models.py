"""SEO metadata, redirects, and content analysis.

``SEOMetadata`` is a generic-relation model with a **nullable** ``site``, and
that nullability is the whole design:

    site = NULL  -> the default metadata for this object, on every site
    site = <id>  -> an override for that one site

Only a ``(object, site)`` row can express "this article is canonical at
example.com but syndicated at partner.com", which is precisely what a
multi-site CMS has to say. Inline columns on ``Article`` could not, and would
also add ~25 columns to the hottest table in the schema and need duplicating
for categories, tags and pages.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q


class SEOMetadata(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    site = models.ForeignKey(
        "tenancy.Site",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="seo_overrides",
        help_text="NULL = default for every site; set = override for that site.",
    )

    # -- core ---------------------------------------------------------
    meta_title = models.CharField(max_length=200, blank=True, default="")
    meta_description = models.TextField(max_length=320, blank=True, default="")
    canonical_url = models.URLField(max_length=500, blank=True, default="")
    focus_keyword = models.CharField(max_length=120, blank=True, default="")
    secondary_keywords = models.JSONField(default=list, blank=True)

    # -- robots -------------------------------------------------------
    robots_index = models.BooleanField(default=True)
    robots_follow = models.BooleanField(default=True)
    robots_noarchive = models.BooleanField(default=False)
    robots_nosnippet = models.BooleanField(default=False)
    robots_noimageindex = models.BooleanField(default=False)
    max_snippet = models.IntegerField(default=-1, help_text="-1 = unset")
    max_image_preview = models.CharField(
        max_length=8,
        default="large",
        choices=[("none", "none"), ("standard", "standard"), ("large", "large")],
    )
    max_video_preview = models.IntegerField(default=-1)
    unavailable_after = models.DateTimeField(null=True, blank=True)

    # -- open graph ---------------------------------------------------
    og_title = models.CharField(max_length=200, blank=True, default="")
    og_description = models.TextField(max_length=400, blank=True, default="")
    og_image = models.URLField(max_length=500, blank=True, default="")
    og_image_alt = models.CharField(max_length=250, blank=True, default="")
    og_type = models.CharField(max_length=32, default="article")
    og_locale = models.CharField(max_length=10, blank=True, default="")

    # -- twitter ------------------------------------------------------
    twitter_card = models.CharField(
        max_length=24,
        default="summary_large_image",
        choices=[
            ("summary", "summary"),
            ("summary_large_image", "summary_large_image"),
            ("player", "player"),
        ],
    )
    twitter_title = models.CharField(max_length=200, blank=True, default="")
    twitter_description = models.TextField(max_length=400, blank=True, default="")
    twitter_image = models.URLField(max_length=500, blank=True, default="")
    twitter_site = models.CharField(max_length=40, blank=True, default="")

    # -- structured data / sitemap ------------------------------------
    schema_type = models.CharField(
        max_length=40,
        default="Article",
        choices=[
            ("Article", "Article"),
            ("BlogPosting", "BlogPosting"),
            ("NewsArticle", "NewsArticle"),
            ("HowTo", "HowTo"),
        ],
    )
    structured_data_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Deep-merged over the generated JSON-LD, last.",
    )
    faq_items = models.JSONField(default=list, blank=True, help_text="[{q, a}, ...]")
    hide_from_sitemap = models.BooleanField(default=False)
    sitemap_priority = models.DecimalField(
        max_digits=2, decimal_places=1, default=Decimal("0.7")
    )
    sitemap_changefreq = models.CharField(max_length=12, default="weekly")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "seo"
        verbose_name = "SEO metadata"
        verbose_name_plural = "SEO metadata"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "site"],
                name="seo_unique_object_site",
            ),
            # A second partial constraint is required: SQL treats NULLs as
            # distinct, so the constraint above would happily allow two
            # "default" rows for the same object.
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                condition=Q(site__isnull=True),
                name="seo_unique_object_default",
            ),
        ]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        scope = self.site.slug if self.site_id else "default"
        return f"SEO({self.content_type_id}:{self.object_id} @ {scope})"


class SEOMixin(models.Model):
    """Adds the reverse generic relation plus resolution helpers."""

    class Meta:
        abstract = True

    @property
    def seo_entries(self):
        return SEOMetadata.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk,
        )

    def resolved_seo(self, site=None, placement=None):
        from .resolver import resolve_seo

        return resolve_seo(self, site=site, placement=placement)


class Redirect(models.Model):
    """A source path that should send visitors somewhere else.

    Consumed in bulk by the front-end middleware rather than queried per
    request, so the whole active set is served from one cached endpoint.
    """

    STATUS_CHOICES = [(301, "301 Permanent"), (302, "302 Found"), (307, "307"), (308, "308")]

    site = models.ForeignKey(
        "tenancy.Site", on_delete=models.CASCADE, related_name="redirects"
    )
    source_path = models.CharField(
        max_length=500, help_text="Always a leading slash, no host."
    )
    target_path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField(default=301, choices=STATUS_CHOICES)
    is_regex = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    hit_count = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=250, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "seo"
        ordering = ["source_path"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "source_path"], name="redirect_unique_site_source"
            )
        ]
        indexes = [models.Index(fields=["site", "is_active", "source_path"])]

    def __str__(self):
        return f"{self.source_path} -> {self.target_path} ({self.status_code})"

    def save(self, *args, **kwargs):
        self.source_path = self._normalise(self.source_path)
        if not self.target_path.startswith(("http://", "https://")):
            self.target_path = self._normalise(self.target_path)
        super().save(*args, **kwargs)
        self._invalidate_cache()

    def delete(self, *args, **kwargs):
        site_id = self.site_id
        super().delete(*args, **kwargs)
        self._invalidate_cache(site_id)

    def _invalidate_cache(self, site_id=None):
        """Drop the cached bundle so a new rule takes effect immediately.

        The public endpoint serves the whole redirect set with a 60s TTL;
        without this an editor would fix a broken link and still see the 404
        for a minute.
        """
        from django.core.cache import cache

        cache.delete(f"pub:{site_id or self.site_id}:redirects")

    @staticmethod
    def _normalise(path: str) -> str:
        path = (path or "").strip()
        if not path:
            return "/"
        if not path.startswith("/"):
            path = "/" + path
        # Collapse a trailing slash so "/a" and "/a/" cannot both exist and
        # disagree about where they point.
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return path


class SEOAnalysis(models.Model):
    """Cached result of running the SEO checks against an article."""

    article = models.OneToOneField(
        "articles.Article", on_delete=models.CASCADE, related_name="seo_analysis"
    )
    site = models.ForeignKey(
        "tenancy.Site", on_delete=models.CASCADE, null=True, blank=True
    )
    score = models.PositiveSmallIntegerField(default=0)
    readability_score = models.PositiveSmallIntegerField(default=0)
    checks = models.JSONField(default=list)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "seo"
        verbose_name_plural = "SEO analyses"

    def __str__(self):
        return f"SEO {self.score}/100 for {self.article_id}"
