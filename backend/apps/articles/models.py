import hashlib
import json
import math
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.editorial.states import LIVE_STATES, PUBLISHED, STATUS_CHOICES
from apps.seo.models import SEOMixin
from common.blocks import blocks_to_plaintext
from common.slugs import unique_slug
from common.tenancy import TenantModel

WORDS_PER_MINUTE = 200


class Article(TenantModel, SEOMixin):
    # Sourced from apps.editorial.states so the field choices and the
    # transition table cannot drift apart. The three original values
    # (draft/published/archived) keep their exact spelling, so the legacy API's
    # `status="published"` filter and every stored row remain valid.
    STATUS_CHOICES = STATUS_CHOICES

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True, allow_unicode=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    content = models.JSONField(
        default=dict,
        help_text="Editor.js block content stored as JSON",
    )
    excerpt = models.TextField(blank=True, default="", max_length=500)
    featured_image = models.URLField(blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    is_featured = models.BooleanField(default=False)
    reading_time = models.PositiveIntegerField(default=0, help_text="Estimated reading time in minutes")
    views_count = models.PositiveIntegerField(default=0)

    # ``published_at`` is the *first* publication date and is deliberately never
    # cleared -- it is what JSON-LD reports as datePublished, and resetting it on
    # an unpublish/republish cycle would rewrite the article's history. Whether
    # the public can currently see the article is ``is_live``, which *is*
    # cleared. The two are always set in lockstep.
    is_live = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the article is currently visible to the public.",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    #: Most recent publication, unlike ``published_at`` which records the first.
    #: Both are needed: JSON-LD wants datePublished stable, while editors and
    #: "recently updated" feeds want to know about a republish.
    last_published_at = models.DateTimeField(null=True, blank=True)
    unpublished_at = models.DateTimeField(null=True, blank=True)

    #: Indexed because the beat sweep filters on it every 60 seconds; without
    #: the index that becomes a sequential scan of the whole table per tick.
    scheduled_publish_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_unpublish_at = models.DateTimeField(null=True, blank=True, db_index=True)

    #: Overrides the site locale for this article when set. Empty means "use
    #: the site's".
    locale = models.CharField(max_length=16, blank=True, default="")
    #: Links locale variants of the same piece. Two articles sharing a group
    #: are translations of each other, and each one's `hreflang` alternates are
    #: the others.
    #:
    #: A plain string rather than a FK to a "TranslationGroup" table: the group
    #: has no attributes of its own, and a table would make creating the second
    #: translation a two-step operation for no gain. Indexed, because the
    #: alternates lookup runs on every article render.
    translation_group = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Derived from ``content`` on every save; see common.blocks.
    plain_text = models.TextField(
        blank=True,
        default="",
        help_text="Flattened block text, including annotation bodies.",
    )
    word_count = models.PositiveIntegerField(default=0)
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="sha256 of the content JSON; drives optimistic concurrency.",
    )

    class Meta:
        app_label = "articles"
        ordering = ["-published_at", "-created_at"]

    #: Recomputed on every save from other fields. Tracked explicitly so that a
    #: narrow ``save(update_fields=...)`` still persists them -- see below.
    DERIVED_FIELDS = frozenset(
        {"is_live", "plain_text", "word_count", "reading_time", "content_hash"}
    )

    def save(self, *args, **kwargs):
        derived = set(self.DERIVED_FIELDS)

        if not self.slug:
            self.slug = unique_slug(
                self.title,
                Article.objects.exclude(pk=self.pk),
                fallback=uuid.uuid4().hex[:8],
            )
            derived.add("slug")

        if self.status == PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
            derived.add("published_at")

        # Visibility is *derived*, never assigned by callers. Transitions set
        # only ``status``; this is the single definition of "the public can see
        # it", so the two can never disagree.
        self.is_live = self.status in LIVE_STATES

        # Derive text metrics from the block content. This delegates to
        # common.blocks, which walks headers, lists, tables, captions and
        # annotation bodies. The previous inline version only read ``text`` and
        # ``items``, so interactive articles -- where much of the prose lives in
        # annotations -- were reported at a fraction of their real length.
        self.plain_text = blocks_to_plaintext(self.content)
        self.word_count = len(self.plain_text.split())
        self.reading_time = max(1, math.ceil(self.word_count / WORDS_PER_MINUTE))
        self.content_hash = self._compute_content_hash()

        # A caller asking to write only `status` still needs the columns this
        # method just recomputed to reach the database. Django writes exactly
        # the listed fields and nothing else, so without this union an article
        # could be marked published while `is_live` stayed False in the row --
        # visible in the studio, invisible to the public, with no error.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = sorted(
                set(update_fields) | derived | {"updated_at"}
            )

        super().save(*args, **kwargs)

    def _compute_content_hash(self) -> str:
        """Stable hash of the content JSON, independent of key ordering."""
        return hashlib.sha256(
            json.dumps(self.content or {}, sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()

    def translations(self):
        """Sibling articles in other locales, excluding this one.

        Cross-site by design: the Bengali edition of a piece may live on a
        different tenant than the English one, and hreflang is precisely the
        tag that tells a search engine those are the same content in different
        languages. Scoping this to one site would make it useless for the case
        it exists to serve.
        """
        if not self.translation_group:
            return Article.unscoped.none()
        return (
            Article.unscoped.filter(
                translation_group=self.translation_group, is_live=True
            )
            .exclude(pk=self.pk)
            .select_related("site")
        )

    def effective_locale(self) -> str:
        """The article's own locale, falling back to its site's."""
        return self.locale or (self.site.locale if self.site_id else "") or "en"

    def __str__(self):
        return self.title
