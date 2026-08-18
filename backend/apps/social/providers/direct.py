"""Direct per-platform providers.

These talk to LinkedIn, X, Facebook and Threads themselves rather than through
the aggregator. They exist to discharge the abstraction's whole purpose:
flipping one ``SocialAccount.provider`` value and re-authenticating must change
**nothing** in the composer, the scheduler, or the dispatch task.

So there is nothing here but ``SocialProvider`` implementations. No new
exception types, no extra call the caller has to know to make, no scheduling.
Threads' two-step publish is expressed with the same ``ProviderNotReady`` the
aggregator already used for it; X's 23-character URL rule is already in the
shared constraints table and needs no code here at all.

Credentials come from ``account.credentials`` (Fernet-decrypted) and the
per-platform app keys from settings. An unconfigured provider raises a
permanent error naming the missing setting, rather than failing at the API with
something unreadable.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

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


class OAuthProvider(SocialProvider):
    """Shared HTTP handling for the direct integrations.

    The status-code mapping is the important part and is identical across all
    four, because it is about *our* retry semantics rather than any platform's
    vocabulary: 401/403 means re-auth, 429 and 5xx mean try later, other 4xx
    means the request is wrong and retrying it unchanged cannot help.
    """

    authorize_url = ""
    token_url = ""
    api_root = ""
    scopes: tuple[str, ...] = ()
    #: (client-id setting, client-secret setting)
    settings_keys: tuple[str, str] = ("", "")

    def _app_credentials(self) -> tuple[str, str]:
        client_id = getattr(settings, self.settings_keys[0], "")
        client_secret = getattr(settings, self.settings_keys[1], "")
        if not client_id or not client_secret:
            raise ProviderError(
                f"{self.key} is not configured; set {self.settings_keys[0]} and "
                f"{self.settings_keys[1]}.",
                permanent=True,
            )
        return client_id, client_secret

    def _token(self) -> str:
        token = (self.account.credentials or {}).get("access_token", "")
        if not token:
            raise ProviderAuthError(f"{self.key}: no access token stored.")
        return token

    def _call(self, method: str, url: str, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", f"Bearer {self._token()}")
        try:
            response = requests.request(
                method,
                url if url.startswith("http") else f"{self.api_root}{url}",
                headers=headers,
                timeout=TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc

        if response.status_code in (401, 403):
            raise ProviderAuthError(
                f"{self.key} rejected the token ({response.status_code}).",
                detail={"body": response.text[:400]},
            )
        if response.status_code == 429:
            raise ProviderNotReady(
                f"{self.key} rate limited.",
                retry_after=int(response.headers.get("Retry-After") or 60),
            )
        if response.status_code >= 500:
            raise ProviderError(f"{self.key} HTTP {response.status_code}")
        if response.status_code >= 400:
            raise ProviderError(
                f"{self.key} HTTP {response.status_code}: {response.text[:400]}",
                permanent=True,
            )
        try:
            return response.json()
        except ValueError:
            return {}

    def begin_authorization(self, *, site, platform, redirect_uri):
        client_id, _ = self._app_credentials()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": site.slug,
        }
        return AuthorizationStart(
            redirect_url=f"{self.authorize_url}?{urlencode(params)}",
            state={"redirect_uri": redirect_uri},
        )

    def _exchange(self, payload: dict, redirect_uri: str) -> dict:
        client_id, client_secret = self._app_credentials()
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": payload.get("code", ""),
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderAuthError(
                f"{self.key} token exchange failed: {response.text[:300]}"
            )
        return response.json()

    def capabilities(self):
        return Capabilities(
            can_delete=True,
            can_fetch_metrics=True,
            can_upload_media=True,
            can_refresh=True,
            # None of the four offer scheduling we would use; ours is ours.
            native_scheduling=False,
        )


@register
class LinkedInProvider(OAuthProvider):
    key = "linkedin_direct"
    platforms = ("linkedin",)
    authorize_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    api_root = "https://api.linkedin.com/v2"
    scopes = ("w_member_social", "r_liteprofile")
    settings_keys = ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET")

    def complete_authorization(self, *, site, platform, payload):
        token = self._exchange(payload, payload.get("redirect_uri", ""))
        self.account = self.account or _Stub(token["access_token"])
        profile = self._call("GET", "/userinfo", headers={
            "Authorization": f"Bearer {token['access_token']}"
        })
        return AccountInfo(
            external_id=str(profile.get("sub") or ""),
            display_name=profile.get("name") or "LinkedIn",
            handle=profile.get("email") or "",
            avatar_url=profile.get("picture") or "",
            credentials={"access_token": token["access_token"]},
            expires_at=None,
        )

    def publish(self, *, platform, caption, media, idempotency_key, state):
        body = {
            "author": f"urn:li:person:{self.account.external_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "IMAGE" if media else "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        result = self._call(
            "POST",
            "/ugcPosts",
            json=body,
            headers={
                "X-Restli-Protocol-Version": "2.0.0",
                # LinkedIn's own dedupe header. Same key we pass everywhere
                # else, so a redelivered task cannot double-post.
                "X-RestLi-Method": "create",
                "x-li-idempotency-key": idempotency_key,
            },
        )
        post_id = str(result.get("id") or "")
        return PublishResult(
            external_id=post_id,
            url=f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "",
            raw=result,
        )


@register
class XProvider(OAuthProvider):
    key = "x_direct"
    platforms = ("x",)
    authorize_url = "https://twitter.com/i/oauth2/authorize"
    token_url = "https://api.twitter.com/2/oauth2/token"
    api_root = "https://api.twitter.com/2"
    scopes = ("tweet.read", "tweet.write", "users.read", "offline.access")
    settings_keys = ("X_CLIENT_ID", "X_CLIENT_SECRET")

    def complete_authorization(self, *, site, platform, payload):
        token = self._exchange(payload, payload.get("redirect_uri", ""))
        self.account = self.account or _Stub(token["access_token"])
        me = self._call("GET", "/users/me", headers={
            "Authorization": f"Bearer {token['access_token']}"
        }).get("data", {})
        return AccountInfo(
            external_id=str(me.get("id") or ""),
            display_name=me.get("name") or "X",
            handle=f"@{me.get('username')}" if me.get("username") else "",
            credentials={
                "access_token": token["access_token"],
                "refresh_token": token.get("refresh_token", ""),
            },
            expires_at=None,
        )

    def refresh_credentials(self):
        refresh = (self.account.credentials or {}).get("refresh_token")
        if not refresh:
            return None
        client_id, client_secret = self._app_credentials()
        response = requests.post(
            self.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            raise ProviderAuthError("X refused to refresh the token.")
        token = response.json()
        return AccountInfo(
            external_id=self.account.external_id,
            display_name=self.account.display_name,
            handle=self.account.handle,
            credentials={
                "access_token": token["access_token"],
                "refresh_token": token.get("refresh_token", refresh),
            },
        )

    def publish(self, *, platform, caption, media, idempotency_key, state):
        body = {"text": caption}
        media_ids = [item["external_id"] for item in media if item.get("external_id")]
        if media_ids:
            body["media"] = {"media_ids": media_ids}
        result = self._call("POST", "/tweets", json=body).get("data", {})
        tweet_id = str(result.get("id") or "")
        return PublishResult(
            external_id=tweet_id,
            url=f"https://x.com/i/status/{tweet_id}" if tweet_id else "",
            raw=result,
        )

    def delete(self, *, external_id):
        self._call("DELETE", f"/tweets/{external_id}")
        return True

    def fetch_metrics(self, *, external_id):
        data = self._call(
            "GET", f"/tweets/{external_id}", params={"tweet.fields": "public_metrics"}
        ).get("data", {})
        metrics = data.get("public_metrics", {})
        return {
            "impressions": metrics.get("impression_count"),
            "likes": metrics.get("like_count"),
            "comments": metrics.get("reply_count"),
            "shares": metrics.get("retweet_count"),
            "fetched_at": timezone.now().isoformat(),
        }


class MetaProvider(OAuthProvider):
    """Shared base for Facebook and Threads -- both are Meta Graph APIs."""

    api_root = "https://graph.facebook.com/v21.0"
    authorize_url = "https://www.facebook.com/v21.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    settings_keys = ("META_APP_ID", "META_APP_SECRET")

    def complete_authorization(self, *, site, platform, payload):
        token = self._exchange(payload, payload.get("redirect_uri", ""))
        self.account = self.account or _Stub(token["access_token"])
        me = self._call(
            "GET", "/me", params={"fields": "id,name,username,picture"},
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        return AccountInfo(
            external_id=str(me.get("id") or ""),
            display_name=me.get("name") or platform,
            handle=me.get("username") or "",
            avatar_url=(me.get("picture") or {}).get("data", {}).get("url", ""),
            credentials={"access_token": token["access_token"]},
        )


@register
class FacebookProvider(MetaProvider):
    key = "facebook_direct"
    platforms = ("facebook",)
    scopes = ("pages_manage_posts", "pages_read_engagement")

    def publish(self, *, platform, caption, media, idempotency_key, state):
        result = self._call(
            "POST",
            f"/{self.account.external_id}/feed",
            json={"message": caption},
        )
        post_id = str(result.get("id") or "")
        return PublishResult(
            external_id=post_id,
            url=f"https://www.facebook.com/{post_id}" if post_id else "",
            raw=result,
        )

    def fetch_metrics(self, *, external_id):
        data = self._call(
            "GET",
            f"/{external_id}/insights",
            params={"metric": "post_impressions,post_engaged_users"},
        )
        values = {
            row.get("name"): (row.get("values") or [{}])[0].get("value")
            for row in data.get("data", [])
        }
        return {
            "impressions": values.get("post_impressions"),
            "clicks": values.get("post_engaged_users"),
            "fetched_at": timezone.now().isoformat(),
        }


@register
class ThreadsProvider(MetaProvider):
    key = "threads_direct"
    platforms = ("threads",)
    api_root = "https://graph.threads.net/v1.0"
    authorize_url = "https://threads.net/oauth/authorize"
    token_url = "https://graph.threads.net/oauth/access_token"
    scopes = ("threads_basic", "threads_content_publish")

    def publish(self, *, platform, caption, media, idempotency_key, state):
        """Two-step: create a container, then publish it.

        Expressed entirely through ``ProviderNotReady``, exactly as the
        aggregator does. The alternative -- a two-phase method on the
        interface -- would push this one platform's quirk onto three providers
        that do not have it, which is what a good abstraction is supposed to
        avoid.
        """
        creation_id = (state or {}).get("creation_id")

        if not creation_id:
            container = self._call(
                "POST",
                f"/{self.account.external_id}/threads",
                json={
                    "media_type": "IMAGE" if media else "TEXT",
                    "text": caption,
                    **(
                        {"image_url": media[0].get("url")}
                        if media and media[0].get("url")
                        else {}
                    ),
                },
            )
            creation_id = str(container.get("id") or "")
            if not creation_id:
                raise ProviderError("Threads returned no container id.", detail=container)
            # Not an error and not a failure: the container exists and needs a
            # moment. The attempt counter must not advance here, or a slow
            # upload burns the retries meant for real problems.
            raise ProviderNotReady(
                "Threads container created; publishing shortly.",
                retry_after=20,
                state={"creation_id": creation_id},
            )

        result = self._call(
            "POST",
            f"/{self.account.external_id}/threads_publish",
            json={"creation_id": creation_id},
        )
        post_id = str(result.get("id") or "")
        return PublishResult(external_id=post_id, url="", raw=result)


class _Stub:
    """Stands in for an account during authorization, before one exists."""

    external_id = ""
    display_name = ""
    handle = ""
    avatar_url = ""

    def __init__(self, access_token: str):
        self.credentials = {"access_token": access_token}
