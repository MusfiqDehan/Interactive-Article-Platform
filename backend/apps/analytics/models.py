"""Content analytics: an append-only event log and its daily rollups.

Replaces the unauthenticated, unthrottled ``views_count`` increment that used
to run on every article read. That endpoint was both a write on the hottest
read path and trivially inflatable by anyone with curl.

Two tables, because they answer different questions and have opposite access
patterns. ``ContentEvent`` is append-only, never updated, and read by the
rollup task. ``DailyContentStat`` is what every dashboard query hits, and is
small enough to index freely.

**No PII.** A session is ``sha256(ip + user-agent + daily salt)``. The salt
rotates every day, so the same visitor is a different session tomorrow --
which makes "unique visitors today" answerable and cross-day tracking of an
individual impossible by construction, rather than by policy.

The event names are chosen so the metric that justifies this product can be
computed: ``annotation_open / view`` is the interaction rate, and nothing in a
generic analytics tool can produce it.
"""

from __future__ import annotations

import hashlib

from django.db import models
from django.utils import timezone

from common.tenancy import TenantModel

EVENT_CHOICES = (
    ("view", "Page view"),
    ("read_complete", "Read to the end"),
    # The differentiating metrics: interaction with the interactive parts.
    ("annotation_open", "Annotation opened"),
    ("hotspot_open", "Image hotspot opened"),
    ("media_play", "Media played"),
    ("chapter_jump", "Chapter jumped to"),
    ("outbound_click", "Outbound link clicked"),
    ("share", "Shared"),
    ("search", "Search performed"),
)
EVENT_NAMES = frozenset(name for name, _ in EVENT_CHOICES)


def session_hash(ip: str, user_agent: str, *, day=None) -> str:
    """A stable-for-one-day, non-reversible visitor identifier.

    The daily salt is what makes this privacy-preserving rather than
    pseudonymous: yesterday's hashes cannot be linked to today's even with the
    original IP, because the input differs.
    """
    from django.conf import settings

    day = day or timezone.now().date()
    salt = f"{getattr(settings, 'SECRET_KEY', '')}:{day.isoformat()}"
    return hashlib.sha256(f"{salt}:{ip}:{user_agent}".encode("utf-8")).hexdigest()[:32]


class ContentEvent(TenantModel):
    """One recorded interaction. Append-only."""

    name = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    article = models.ForeignKey(
        "articles.Article",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
    )
    #: Which annotation/hotspot/chapter, where the event has one.
    target_id = models.CharField(max_length=100, blank=True, default="")
    path = models.CharField(max_length=500, blank=True, default="")
    referrer = models.CharField(max_length=500, blank=True, default="")
    locale = models.CharField(max_length=10, blank=True, default="")
    session = models.CharField(max_length=32, db_index=True)
    #: Free-form, small. Deliberately not indexed -- it is for after-the-fact
    #: investigation, not for querying.
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "analytics"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            # The rollup's scan.
            models.Index(fields=["site", "occurred_at"]),
            # Per-article dashboards.
            models.Index(fields=["article", "name", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.name} @ {self.occurred_at:%Y-%m-%d %H:%M}"


class DailyContentStat(TenantModel):
    """One row per (article, day). What every dashboard reads."""

    article = models.ForeignKey(
        "articles.Article",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    day = models.DateField(db_index=True)

    views = models.PositiveIntegerField(default=0)
    unique_sessions = models.PositiveIntegerField(default=0)
    reads_completed = models.PositiveIntegerField(default=0)
    annotation_opens = models.PositiveIntegerField(default=0)
    hotspot_opens = models.PositiveIntegerField(default=0)
    media_plays = models.PositiveIntegerField(default=0)
    outbound_clicks = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "analytics"
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "article", "day"], name="dailystat_unique_site_article_day"
            )
        ]
        indexes = [models.Index(fields=["site", "day"])]

    def __str__(self):
        return f"{self.article_id} on {self.day}"

    @property
    def interaction_rate(self) -> float:
        """Annotation opens per view.

        The headline metric for this product, and the one no competitor can
        report: it measures whether the interactive format is being used, not
        just served. A high view count with a near-zero rate means the
        annotations are decoration.
        """
        if not self.views:
            return 0.0
        return round(self.annotation_opens / self.views, 4)

    @property
    def completion_rate(self) -> float:
        if not self.views:
            return 0.0
        return round(self.reads_completed / self.views, 4)
