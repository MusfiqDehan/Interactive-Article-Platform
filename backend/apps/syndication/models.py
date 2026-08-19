"""Distribution: where content goes, and what happened when it got there.

Three models, three distinct questions:

* ``Placement`` -- *which article appears on which site, at what URL.*
  ``Article.site`` records ownership; a placement records distribution, so an
  article owned by site A can appear on B and C with its own path and its own
  title/excerpt override on each.
* ``Destination`` -- *where content can be pushed*: another site, a partner
  API, a webhook receiver, a feed.
* ``ContentDelivery`` -- *the audit trail per (article, destination)*: state,
  attempts, what was sent, what came back, and when the next try is due.

The single most important field here is ``Placement.canonical_to_primary``. A
syndicated copy defaults to pointing its canonical URL back at the owning site,
which is what stops the same content competing with itself in search results.

The second is ``ContentDelivery.idempotency_key``. It hashes
``(destination, article, event, fingerprint)``, where the fingerprint covers
everything a receiver renders -- see ``delivery.payload_fingerprint``.
Re-publishing unchanged content therefore produces a key that already exists
and sends nothing, while any real edit produces a new one. That is what makes
the delivery worker safe to retry, and it must be: Celery acks late and will
re-run a task whose worker died mid-POST.
"""

from __future__ import annotations

import hashlib
import secrets

from django.db import models
from django.db.models import Q
from django.utils import timezone

from common.retry import MAX_ATTEMPTS, backoff_seconds


class PlacementQuerySet(models.QuerySet):
    def live(self):
        return self.filter(is_live=True)

    def for_site(self, site):
        if site is None:
            return self.none()
        return self.filter(site=site)


class Placement(models.Model):
    article = models.ForeignKey(
        "articles.Article", on_delete=models.CASCADE, related_name="placements"
    )
    site = models.ForeignKey(
        "tenancy.Site", on_delete=models.CASCADE, related_name="placements"
    )

    path_slug = models.SlugField(
        max_length=300,
        allow_unicode=True,
        help_text="URL slug on this site; may differ from the article's own slug.",
    )
    is_primary = models.BooleanField(
        default=False, help_text="True for the owning site's placement."
    )
    is_live = models.BooleanField(default=False, db_index=True)
    canonical_to_primary = models.BooleanField(
        default=True,
        help_text="Point rel=canonical at the owning site rather than self.",
    )

    override_title = models.CharField(max_length=300, blank=True, default="")
    override_excerpt = models.TextField(max_length=500, blank=True, default="")

    published_at = models.DateTimeField(null=True, blank=True)
    order = models.IntegerField(default=0, help_text="Manual curation order.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlacementQuerySet.as_manager()

    class Meta:
        app_label = "syndication"
        ordering = ["order", "-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "site"], name="placement_unique_article_site"
            ),
            models.UniqueConstraint(
                fields=["site", "path_slug"], name="placement_unique_site_path"
            ),
            models.UniqueConstraint(
                fields=["article"],
                condition=Q(is_primary=True),
                name="placement_single_primary",
            ),
        ]
        indexes = [
            models.Index(fields=["site", "is_live", "-published_at"]),
        ]

    def __str__(self):
        return f"{self.article_id} on {self.site_id}: /{self.path_slug}"

    @property
    def url(self) -> str:
        return self.site.url_for(f"articles/{self.path_slug}")

    def resolved_canonical(self) -> str:
        """The canonical URL a crawler should be told about for this placement."""
        if self.is_primary or not self.canonical_to_primary:
            return self.url
        primary = (
            Placement.objects.select_related("site")
            .filter(article_id=self.article_id, is_primary=True)
            .first()
        )
        return primary.url if primary else self.url

    @property
    def title(self) -> str:
        return self.override_title or self.article.title

    @property
    def excerpt(self) -> str:
        return self.override_excerpt or self.article.excerpt


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------


class Destination(models.Model):
    """Somewhere content can be pushed.

    Separate from ``Site``: a site is a tenant we own and render, while a
    destination is an outbound channel, which may be a site, a partner's API,
    or a webhook receiver with no notion of pages at all. Collapsing the two
    would mean every partner integration needed a full tenant row.
    """

    KIND_CHOICES = (
        ("site", "Owned site"),
        ("partner_api", "Partner API"),
        ("webhook", "Webhook"),
        ("rss", "RSS feed"),
        ("newsletter", "Newsletter"),
    )

    site = models.ForeignKey(
        "tenancy.Site",
        on_delete=models.CASCADE,
        related_name="destinations",
        help_text="The tenant that owns this destination.",
    )
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="webhook")

    #: For `site` destinations, the site content is delivered *to*.
    target_site = models.ForeignKey(
        "tenancy.Site",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="inbound_destinations",
    )
    endpoint_url = models.URLField(max_length=500, blank=True, default="")
    #: Shared with the receiver out of band. Never returned by the API.
    secret = models.CharField(max_length=128, blank=True, default="")
    headers = models.JSONField(
        default=dict, blank=True, help_text="Extra static headers to send."
    )
    events = models.JSONField(
        default=list,
        blank=True,
        help_text="Event names to deliver; empty means all.",
    )

    is_active = models.BooleanField(default=True)
    #: Set when the endpoint has failed so consistently that continuing to
    #: retry is only generating load. Cleared by a human re-enabling it.
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=250, blank=True, default="")
    consecutive_failures = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #: After this many failures in a row with no success in between, the
    #: destination is switched off. A permanently broken receiver would
    #: otherwise consume a worker slot on every publish, indefinitely.
    FAILURE_LIMIT = 20

    class Meta:
        app_label = "syndication"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "name"], name="destination_unique_site_name"
            )
        ]
        indexes = [models.Index(fields=["site", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.kind})"

    def save(self, *args, **kwargs):
        if not self.secret and self.kind in ("webhook", "partner_api", "site"):
            # Generated rather than required: a destination created without one
            # would otherwise sign with an empty secret, which `common.signing`
            # refuses -- turning a configuration slip into a delivery that never
            # leaves the queue.
            self.secret = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_deliverable(self) -> bool:
        return self.is_active and self.disabled_at is None

    def accepts(self, event: str) -> bool:
        return not self.events or event in self.events

    def resolved_url(self) -> str:
        if self.kind == "site" and self.target_site_id:
            return self.target_site.url_for("api/revalidate")
        return self.endpoint_url

    def record_success(self):
        if self.consecutive_failures:
            type(self).objects.filter(pk=self.pk).update(consecutive_failures=0)
            self.consecutive_failures = 0

    def record_failure(self, reason: str = ""):
        """Count a failure and disable the destination once it is hopeless.

        Uses an F-expression rather than read-modify-write: several deliveries
        to the same destination fail concurrently by construction, and
        incrementing in Python would lose most of them.
        """
        type(self).objects.filter(pk=self.pk).update(
            consecutive_failures=models.F("consecutive_failures") + 1
        )
        self.refresh_from_db(fields=["consecutive_failures"])
        if self.consecutive_failures >= self.FAILURE_LIMIT and self.disabled_at is None:
            self.disabled_at = timezone.now()
            self.disabled_reason = (
                f"{self.consecutive_failures} consecutive failures. {reason}".strip()
            )[:250]
            self.save(update_fields=["disabled_at", "disabled_reason"])


class ContentDelivery(models.Model):
    """One attempt-tracked delivery of one article to one destination."""

    STATE_CHOICES = (
        ("pending", "Pending"),
        ("delivering", "Delivering"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("abandoned", "Abandoned"),
        ("skipped", "Skipped"),
    )
    EVENT_CHOICES = (
        ("publish", "Published"),
        ("update", "Updated"),
        ("unpublish", "Unpublished"),
        ("delete", "Deleted"),
    )

    destination = models.ForeignKey(
        Destination, on_delete=models.CASCADE, related_name="deliveries"
    )
    article = models.ForeignKey(
        "articles.Article",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deliveries",
    )
    #: Kept denormalised so the log still reads sensibly after the article is
    #: deleted -- which is precisely when someone wants to look at it.
    article_label = models.CharField(max_length=300, blank=True, default="")

    event = models.CharField(max_length=16, choices=EVENT_CHOICES, default="publish")
    state = models.CharField(
        max_length=16, choices=STATE_CHOICES, default="pending", db_index=True
    )

    #: sha256(destination:article:event:content_hash). Unique, and that
    #: uniqueness *is* the idempotency guarantee -- see the module docstring.
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    #: Sent as X-CMS-Event-Id so a receiver can dedupe on its own side too.
    event_id = models.CharField(max_length=36, db_index=True)

    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True, default="")
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)

    payload_snapshot = models.JSONField(default=dict, blank=True)
    response_snapshot = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "syndication"
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "Content deliveries"
        indexes = [
            models.Index(fields=["destination", "state"]),
            # The sweep's query: due, retryable rows in time order.
            models.Index(fields=["state", "next_attempt_at"]),
        ]

    def __str__(self):
        return f"{self.event} {self.article_label} -> {self.destination_id} [{self.state}]"

    @staticmethod
    def key_for(destination_id: int, article_id, event: str, content_hash: str) -> str:
        raw = f"{destination_id}:{article_id}:{event}:{content_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def is_retryable(self) -> bool:
        return self.state in ("pending", "failed") and self.attempts < MAX_ATTEMPTS

    def schedule_retry(self, error: str = ""):
        """Record a failure and set the next attempt, or give up."""
        self.attempts += 1
        self.last_error = (error or "")[:2000]
        if self.attempts >= MAX_ATTEMPTS:
            self.state = "abandoned"
            self.next_attempt_at = None
        else:
            self.state = "failed"
            self.next_attempt_at = timezone.now() + timezone.timedelta(
                seconds=backoff_seconds(self.attempts + 1)
            )
        self.save(
            update_fields=[
                "attempts", "last_error", "state", "next_attempt_at", "updated_at",
            ]
        )

    def mark_delivered(self, status_code: int, body):
        self.attempts += 1
        self.state = "delivered"
        self.response_status = status_code
        self.response_snapshot = body if isinstance(body, dict) else {"body": str(body)[:2000]}
        self.delivered_at = timezone.now()
        self.next_attempt_at = None
        self.last_error = ""
        self.save(
            update_fields=[
                "attempts", "state", "response_status", "response_snapshot",
                "delivered_at", "next_attempt_at", "last_error", "updated_at",
            ]
        )
