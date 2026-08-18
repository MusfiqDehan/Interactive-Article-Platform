"""Social accounts, posts, and per-platform targets.

The shape is three levels because a "share" is three different things at once:

* ``SocialPost`` -- one editorial act. "Share this article." It is what the
  composer creates and what a schedule refers to.
* ``SocialPostTarget`` -- one platform's copy of it, with its own caption,
  media, state, retries and metrics. **This is where publishing actually
  happens**, and the reason it is a row rather than a column: an oversized
  image on X must fail that target and leave LinkedIn published, which is
  impossible if the post has a single state.
* ``SocialAccount`` -- the credential a target publishes through.

Credentials are encrypted at rest with Fernet. Not because the database is
expected to leak, but because an OAuth token for a company's LinkedIn page is
the kind of thing that ends up in a `pg_dump` on a laptop, and a token in
plaintext there is a compromise with no detection story.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.tenancy import TenantModel

from .constraints import PLATFORM_CHOICES

logger = logging.getLogger(__name__)


def _fernet():
    """Build the cipher from ``SOCIAL_CREDENTIAL_KEY``.

    Deliberately raises when the key is missing rather than falling back to
    plaintext: a silent fallback would mean credentials stored unencrypted in
    exactly the environment where nobody configured encryption.
    """
    from cryptography.fernet import Fernet

    key = getattr(settings, "SOCIAL_CREDENTIAL_KEY", "")
    if not key:
        raise RuntimeError(
            "SOCIAL_CREDENTIAL_KEY is not set; refusing to store credentials "
            "in plaintext. Generate one with Fernet.generate_key()."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class SocialAccount(TenantModel):
    """A connected account or page on one platform."""

    STATUS_CHOICES = (
        ("connected", "Connected"),
        ("expired", "Token expired"),
        ("revoked", "Revoked"),
        ("error", "Error"),
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    #: Which implementation publishes for this account. Swapping an account
    #: from the aggregator to a direct integration is an UPDATE to this field
    #: plus a re-auth -- nothing above `get_provider()` knows the difference.
    provider = models.CharField(
        max_length=40,
        default="aggregator",
        help_text="Registry key of the provider implementation.",
    )

    display_name = models.CharField(max_length=200)
    handle = models.CharField(max_length=200, blank=True, default="")
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    #: The platform's own id for this account/page.
    external_id = models.CharField(max_length=200, blank=True, default="")

    #: Fernet ciphertext. Never read directly -- use `credentials`.
    encrypted_credentials = models.BinaryField(blank=True, default=b"")
    token_expires_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="connected")
    status_detail = models.CharField(max_length=250, blank=True, default="")
    last_used_at = models.DateTimeField(null=True, blank=True)

    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "social"
        ordering = ["platform", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "platform", "external_id"],
                name="socialaccount_unique_site_platform_external",
            )
        ]
        indexes = [models.Index(fields=["site", "platform", "status"])]

    def __str__(self):
        return f"{self.display_name} ({self.platform})"

    # -- credentials ----------------------------------------------------

    @property
    def credentials(self) -> dict:
        if not self.encrypted_credentials:
            return {}
        try:
            return json.loads(_fernet().decrypt(bytes(self.encrypted_credentials)))
        except Exception:
            # A key rotation without re-encryption lands here. Log and return
            # empty so the account reads as unusable rather than 500ing every
            # page that lists accounts.
            logger.exception("Could not decrypt credentials for account %s", self.pk)
            return {}

    @credentials.setter
    def credentials(self, value: dict):
        self.encrypted_credentials = _fernet().encrypt(
            json.dumps(value or {}).encode("utf-8")
        )

    @property
    def is_usable(self) -> bool:
        if self.status != "connected":
            return False
        if self.token_expires_at and self.token_expires_at <= timezone.now():
            return False
        return True

    def mark_expired(self, detail: str = ""):
        self.status = "expired"
        self.status_detail = detail[:250]
        self.save(update_fields=["status", "status_detail", "updated_at"])


class SocialTemplate(TenantModel):
    """A reusable caption pattern.

    Placeholders: ``{title}`` ``{excerpt}`` ``{link}`` ``{hashtags}``.
    """

    name = models.CharField(max_length=120)
    platform = models.CharField(
        max_length=20, choices=PLATFORM_CHOICES, blank=True, default="",
        help_text="Blank means it applies to any platform.",
    )
    body = models.TextField()
    hashtags = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "social"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SocialPost(TenantModel):
    """One editorial share, fanned out to one or more platforms."""

    STATE_CHOICES = (
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("publishing", "Publishing"),
        ("published", "Published"),
        ("partial", "Partially published"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    article = models.ForeignKey(
        "articles.Article",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="social_posts",
    )
    article_label = models.CharField(max_length=300, blank=True, default="")

    state = models.CharField(
        max_length=16, choices=STATE_CHOICES, default="draft", db_index=True
    )
    #: Honoured by *our* beat task, never handed to the platform. A direct
    #: adapter has no scheduling API, so using an aggregator's would make the
    #: semantics change the day we swap -- exactly what the abstraction exists
    #: to prevent.
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "social"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["site", "state", "scheduled_at"])]

    def __str__(self):
        return f"{self.article_label or 'Post'} [{self.state}]"

    def recompute_state(self):
        """Derive the post's state from its targets.

        ``partial`` is a first-class outcome, not a rounding of "failed": the
        three platforms that did publish are live, and telling the editor
        "failed" would have them re-post to all four.
        """
        states = list(self.targets.values_list("state", flat=True))
        if not states:
            return self.state
        if all(s == "published" for s in states):
            new_state = "published"
        elif any(s == "published" for s in states) and any(
            s in ("failed", "cancelled") for s in states
        ):
            new_state = "partial"
        elif all(s in ("failed", "cancelled") for s in states):
            new_state = "failed"
        elif any(s in ("publishing", "pending", "retrying") for s in states):
            new_state = "publishing"
        else:
            new_state = self.state

        if new_state != self.state:
            self.state = new_state
            self.save(update_fields=["state", "updated_at"])
        return new_state


class SocialPostTarget(models.Model):
    """One platform's copy of a post: its caption, media, state and metrics."""

    STATE_CHOICES = (
        ("pending", "Pending"),
        ("publishing", "Publishing"),
        ("retrying", "Retrying"),
        ("published", "Published"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name="targets")
    account = models.ForeignKey(
        SocialAccount, on_delete=models.CASCADE, related_name="targets"
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    caption = models.TextField(blank=True, default="")
    #: ``[{"url": ..., "alt": ..., "mime": ..., "bytes": ...}]``
    media = models.JSONField(default=list, blank=True)

    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    external_id = models.CharField(max_length=200, blank=True, default="")
    external_url = models.URLField(max_length=500, blank=True, default="")
    #: Provider scratch space that must survive a retry. Threads' two-step
    #: publish stores its `creation_id` here so a retry resumes the container
    #: rather than creating a second one -- which would post twice.
    request_snapshot = models.JSONField(default=dict, blank=True)
    response_snapshot = models.JSONField(default=dict, blank=True)

    metrics = models.JSONField(default=dict, blank=True)
    metrics_fetched_at = models.DateTimeField(null=True, blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "social"
        ordering = ["platform"]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "account"], name="socialtarget_unique_post_account"
            )
        ]
        indexes = [models.Index(fields=["state", "next_attempt_at"])]

    def __str__(self):
        return f"{self.platform} target for post {self.post_id} [{self.state}]"

    def mark_published(self, external_id: str, url: str, response=None):
        self.state = "published"
        self.external_id = external_id or ""
        self.external_url = url or ""
        self.response_snapshot = response if isinstance(response, dict) else {}
        self.published_at = timezone.now()
        self.next_attempt_at = None
        self.last_error = ""
        self.save(
            update_fields=[
                "state", "external_id", "external_url", "response_snapshot",
                "published_at", "next_attempt_at", "last_error", "updated_at",
            ]
        )

    def mark_failed(self, error: str):
        self.state = "failed"
        self.last_error = (error or "")[:2000]
        self.next_attempt_at = None
        self.save(
            update_fields=["state", "last_error", "next_attempt_at", "updated_at"]
        )
