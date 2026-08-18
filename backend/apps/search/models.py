"""Indexing bookkeeping.

``IndexingLog`` exists because the index and the database *will* disagree.
Meilisearch is a separate process; it can be restarting, full, or unreachable
at the exact moment a publish fires. Indexing is best-effort by design -- a
failed index must never fail a publish -- and that trade is only acceptable if
something notices afterwards.

So every indexing attempt records its outcome, and a beat task re-tries the
failures. This is the drift-repair half of "search can be down and publishing
still works".
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from common.tenancy import TenantModel


class IndexingLog(TenantModel):
    ACTION_CHOICES = (("upsert", "Upsert"), ("delete", "Delete"))
    STATE_CHOICES = (
        ("pending", "Pending"),
        ("indexed", "Indexed"),
        ("failed", "Failed"),
    )

    article = models.ForeignKey(
        "articles.Article",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="indexing_logs",
    )
    #: Kept so a delete can still be replayed after the row is gone.
    article_pk = models.PositiveBigIntegerField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default="upsert")
    state = models.CharField(
        max_length=10, choices=STATE_CHOICES, default="pending", db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    #: Detects the other kind of drift: an index entry that succeeded but is
    #: now stale because the article changed and the reindex was lost.
    content_hash = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "search"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "article_pk", "action"],
                name="indexinglog_unique_site_article_action",
            )
        ]
        indexes = [models.Index(fields=["state", "updated_at"])]

    def __str__(self):
        return f"{self.action} {self.article_pk} [{self.state}]"

    def mark(self, state: str, error: str = "", content_hash: str | None = None):
        """Record an attempt's outcome.

        ``content_hash`` is written here rather than assigned by the caller:
        `save(update_fields=...)` writes exactly the listed columns, so an
        assignment outside this method is silently dropped -- and the symptom
        would be drift repair believing every indexed article is stale.
        """
        self.state = state
        self.attempts += 1
        self.last_error = error[:1000]
        if content_hash is not None:
            self.content_hash = content_hash
        self.updated_at = timezone.now()
        self.save(
            update_fields=[
                "state", "attempts", "last_error", "content_hash", "updated_at",
            ]
        )
