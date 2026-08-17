"""Editorial workflow records: revisions, review, and the audit trail."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from common.tenancy import TenantModel


class Revision(TenantModel):
    """An immutable point-in-time snapshot of an article.

    A custom model rather than ``django-reversion``. Reversion stores an opaque
    serialised blob aimed at restoring Django admin objects; the studio needs
    *block-level* diffs of an Editor.js array alongside the SEO and placement
    state captured at the same instant. A JSON ``snapshot`` with a monotonic
    per-article ``number`` gives that directly, and lets the diff run in the
    database's JSON operators rather than after deserialising every version.
    """

    article = models.ForeignKey(
        "articles.Article", on_delete=models.CASCADE, related_name="revisions"
    )
    #: Monotonic per article, starting at 1. Allocated under a row lock in
    #: ``create_revision`` -- a MAX()+1 read outside a lock races two concurrent
    #: saves into the same number and violates the unique constraint.
    number = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    #: The article's workflow state *at the moment of capture*, so the history
    #: reads as a story ("v4 draft -> v5 published") without joining the log.
    status = models.CharField(max_length=20, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="article_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Why this snapshot was taken, e.g. 'published' or 'manual save'.",
    )
    is_autosave = models.BooleanField(default=False)

    class Meta:
        app_label = "editorial"
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "number"], name="uniq_revision_number_per_article"
            )
        ]
        indexes = [models.Index(fields=["article", "-created_at"])]

    def __str__(self):
        return f"{self.article_id} v{self.number}"


class AuditLogEntry(TenantModel):
    """Append-only record of who changed what.

    Deliberately denormalised: ``actor_label`` and ``target_label`` are copied
    in at write time so the trail still reads correctly after a user or article
    is deleted. An audit log that goes blank when the subject is removed is
    worse than none, because it looks complete.
    """

    ACTION_CHOICES = (
        ("transition", "State transition"),
        ("create", "Created"),
        ("update", "Updated"),
        ("delete", "Deleted"),
        ("schedule", "Scheduled"),
        ("unschedule", "Unscheduled"),
        ("revision_restore", "Revision restored"),
        ("review_assign", "Review assigned"),
        ("review_resolve", "Review resolved"),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    actor_label = models.CharField(max_length=200, blank=True, default="")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    #: Nullable FK plus a label: the row survives the article's deletion.
    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    target_label = models.CharField(max_length=300, blank=True, default="")
    from_state = models.CharField(max_length=20, blank=True, default="")
    to_state = models.CharField(max_length=20, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "editorial"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["article", "-created_at"]),
            models.Index(fields=["site", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.actor_label} {self.action} {self.target_label}"


class ReviewAssignment(TenantModel):
    """A request for a named person to review an article."""

    STATE_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("changes_requested", "Changes requested"),
        ("cancelled", "Cancelled"),
    )

    article = models.ForeignKey(
        "articles.Article", on_delete=models.CASCADE, related_name="review_assignments"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews_requested",
    )
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="pending")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "editorial"
        ordering = ["-created_at"]
        constraints = [
            # One *open* request per (article, assignee); resolved ones may
            # accumulate as history. A plain unique_together would block ever
            # asking the same reviewer for a second look.
            models.UniqueConstraint(
                fields=["article", "assignee"],
                condition=models.Q(state="pending"),
                name="uniq_open_review_per_assignee",
            )
        ]

    def __str__(self):
        return f"review of {self.article_id} by {self.assignee_id}"


class ReviewComment(TenantModel):
    """A comment, optionally anchored to an Editor.js block.

    ``block_id`` is why block ids must be stable across saves: if they churn,
    every anchored comment silently detaches from the text it refers to.
    """

    article = models.ForeignKey(
        "articles.Article", on_delete=models.CASCADE, related_name="review_comments"
    )
    block_id = models.CharField(max_length=64, blank=True, default="")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_comments",
    )
    body = models.TextField()
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "editorial"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["article", "is_resolved"])]

    def __str__(self):
        return f"comment on {self.article_id}"
