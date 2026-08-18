"""Aggregator provider: one integration, four platforms.

The first implementation, chosen so the product ships without four separate
OAuth reviews. Everything above it is written against ``SocialProvider``, so
replacing it per-platform later is an ``UPDATE`` and a re-auth.

Two things this deliberately does **not** do:

* **It does not use the aggregator's scheduling.** ``SocialPost.scheduled_at``
  is honoured by our own beat task and this provider is called at the due
  moment. A direct platform integration has no scheduling API at all, so
  leaning on the aggregator's would mean the semantics silently change on the
  day we swap -- which is precisely the coupling the abstraction exists to
  prevent.
* **It does not swallow "not ready".** Threads' container upload gets a typed
  ``ProviderNotReady`` with the ``creation_id`` in its state, so the retry
  resumes the same container instead of creating a second one and posting
  twice.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.utils import timezone

from .base import (
    AccountInfo,
    AuthorizationStart,
    Capabilities,
    ProviderAuthError,
    ProviderError,
    ProviderNotReady,
    PublishResult,
    SocialProvider,
)
from .registry import register

logger = logging.getLogger(__name__)

TIMEOUT = 20


@register
class AggregatorProvider(SocialProvider):
    key = "aggregator"
    platforms = ("x", "linkedin", "facebook", "threads")

    # -- plumbing -------------------------------------------------------

    @property
    def base_url(self) -> str:
        return getattr(settings, "SOCIAL_AGGREGATOR_URL", "").rstrip("/")

    @property
    def api_key(self) -> str:
        return getattr(settings, "SOCIAL_AGGREGATOR_KEY", "")

    def _request(self, method: str, path: str, **kwargs):
        if not self.base_url or not self.api_key:
            raise ProviderError(
                "The social aggregator is not configured "
                "(SOCIAL_AGGREGATOR_URL / SOCIAL_AGGREGATOR_KEY).",
                permanent=True,
            )
        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", f"Bearer {self.api_key}")
        headers.setdefault("Content-Type", "application/json")
        try:
            response = requests.request(
                method, f"{self.base_url}{path}", headers=headers, timeout=TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            # Transport failures are retryable by definition -- nothing about
            # the request was rejected, it never arrived.
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc

        if response.status_code in (401, 403):
            raise ProviderAuthError(
                f"The aggregator rejected our credentials ({response.status_code}).",
                detail={"body": response.text[:500]},
            )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After") or 60)
            raise ProviderNotReady("Rate limited.", retry_after=retry_after)
        if 400 <= response.status_code < 500:
            # A 4xx is the platform telling us the request is wrong. Retrying
            # an identical wrong request cannot help.
            raise ProviderError(
                f"HTTP {response.status_code}: {response.text[:500]}",
                permanent=True,
                detail={"status": response.status_code},
            )
        if response.status_code >= 500:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:300]}")

        try:
            return response.json()
        except ValueError:
            return {}

    # -- account lifecycle ---------------------------------------------

    def begin_authorization(self, *, site, platform, redirect_uri):
        body = self._request(
            "POST",
            "/auth/start",
            json={"platform": platform, "redirect_uri": redirect_uri, "ref": site.slug},
        )
        url = body.get("redirect_url") or body.get("url")
        if not url:
            raise ProviderError("The aggregator did not return an authorization URL.")
        return AuthorizationStart(redirect_url=url, state=body.get("state") or {})

    def complete_authorization(self, *, site, platform, payload):
        body = self._request("POST", "/auth/complete", json={"platform": platform, **payload})
        account = body.get("account") or body
        expires = account.get("expires_at")
        return AccountInfo(
            external_id=str(account.get("id") or account.get("external_id") or ""),
            display_name=account.get("name") or account.get("display_name") or platform,
            handle=account.get("handle") or "",
            avatar_url=account.get("avatar_url") or "",
            credentials={"account_token": account.get("token") or body.get("token") or ""},
            expires_at=expires,
        )

    def refresh_credentials(self):
        token = (self.account.credentials or {}).get("account_token")
        if not token:
            return None
        body = self._request("POST", "/auth/refresh", json={"token": token})
        return AccountInfo(
            external_id=self.account.external_id,
            display_name=self.account.display_name,
            handle=self.account.handle,
            avatar_url=self.account.avatar_url,
            credentials={"account_token": body.get("token") or token},
            expires_at=body.get("expires_at"),
        )

    # -- publishing -----------------------------------------------------

    def upload_media(self, *, platform, media):
        if not media:
            return []
        body = self._request(
            "POST",
            "/media",
            json={
                "platform": platform,
                "account_id": self.account.external_id,
                "items": [
                    {"url": item.get("url"), "alt": item.get("alt", "")} for item in media
                ],
            },
        )
        return body.get("items") or media

    def publish(self, *, platform, caption, media, idempotency_key, state):
        # Resume rather than restart. Without this a retry after a slow
        # container upload creates a *second* container and the account posts
        # twice -- the exact failure two-step publishing invites.
        creation_id = (state or {}).get("creation_id")

        payload = {
            "platform": platform,
            "account_id": self.account.external_id,
            "text": caption,
            "media": media,
            # The aggregator dedupes on this, and so does the platform behind
            # it. It is what makes a redelivered Celery task safe.
            "idempotency_key": idempotency_key,
        }
        if creation_id:
            payload["creation_id"] = creation_id

        body = self._request("POST", "/posts", json=payload)

        status = (body.get("status") or "").lower()
        if status in ("pending", "processing", "in_progress"):
            raise ProviderNotReady(
                f"{platform} is still processing the upload.",
                retry_after=int(body.get("retry_after") or 30),
                # Carried forward so the next attempt continues this container.
                state={"creation_id": body.get("creation_id") or creation_id or ""},
            )
        if status in ("failed", "error"):
            raise ProviderError(
                body.get("error") or "The platform rejected the post.",
                permanent=bool(body.get("permanent")),
                detail=body,
            )

        external_id = str(body.get("id") or body.get("post_id") or "")
        if not external_id:
            raise ProviderError("The aggregator returned no post id.", detail=body)
        return PublishResult(
            external_id=external_id, url=body.get("url") or "", raw=body
        )

    def delete(self, *, external_id):
        self._request("DELETE", f"/posts/{external_id}")
        return True

    def fetch_metrics(self, *, external_id):
        body = self._request("GET", f"/posts/{external_id}/metrics")
        return {
            "impressions": body.get("impressions"),
            "likes": body.get("likes"),
            "comments": body.get("comments"),
            "shares": body.get("shares"),
            "clicks": body.get("clicks"),
            "fetched_at": timezone.now().isoformat(),
        }

    def capabilities(self):
        return Capabilities(
            can_delete=True,
            can_fetch_metrics=True,
            can_upload_media=True,
            can_refresh=True,
            # True, and deliberately unused -- see the module docstring.
            native_scheduling=True,
        )
