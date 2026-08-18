"""The provider contract.

Everything above ``get_provider()`` -- the composer, the scheduler, the
dispatch task, the metrics sweep -- is written against this interface and
knows nothing about which implementation is behind it. That is the whole
point: moving LinkedIn from the aggregator to a direct integration should be
one ``UPDATE social_socialaccount SET provider='linkedin_direct'`` plus a
re-auth, with zero changes to the UI or the scheduling.

Three design notes:

**Publishing takes an idempotency key.** The dispatch task can be redelivered
(Celery acks late) and the network can fail after the platform accepted the
post. Without a key, both cases post twice.

**"Not ready" is a typed answer, not an error.** Threads uploads media to a
container and publishes it a moment later. Modelling that as a two-phase API
would push a platform quirk into the interface every other platform has to
ignore; instead the provider raises ``ProviderNotReady(retry_after=...)`` and
the caller tries again, with ``request_snapshot`` carrying whatever the
provider needs to resume.

**Capabilities are probed, not assumed.** ``capabilities()`` lets the UI grey
out what a given provider cannot do -- deleting a published post, say -- rather
than offering a button that always errors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Publishing failed. Retryable unless ``permanent`` is set."""

    def __init__(self, message: str, *, permanent: bool = False, detail=None):
        super().__init__(message)
        self.permanent = permanent
        self.detail = detail or {}


class ProviderNotReady(Exception):
    """The platform accepted the work but has not finished it yet.

    Carries ``retry_after`` so the caller can wait the right amount rather
    than guessing, and is explicitly *not* a failure -- the attempt counter
    should not advance on it, or a slow container upload would exhaust the
    retries meant for real errors.
    """

    def __init__(self, message: str = "Not ready", *, retry_after: int = 30, state=None):
        super().__init__(message)
        self.retry_after = retry_after
        #: Merged into the target's `request_snapshot` so a retry resumes.
        self.state = state or {}


class ProviderAuthError(ProviderError):
    """The credential is expired or revoked; a human must re-connect."""

    def __init__(self, message: str = "Re-authentication required", detail=None):
        super().__init__(message, permanent=True, detail=detail)


@dataclass(frozen=True)
class PublishResult:
    external_id: str
    url: str = ""
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationStart:
    """Where to send the user, and what to remember while they are away."""

    redirect_url: str
    state: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AccountInfo:
    external_id: str
    display_name: str
    handle: str = ""
    avatar_url: str = ""
    credentials: dict = field(default_factory=dict)
    expires_at=None


@dataclass(frozen=True)
class Capabilities:
    can_delete: bool = False
    can_fetch_metrics: bool = False
    can_upload_media: bool = True
    can_refresh: bool = False
    #: True when the provider itself offers scheduling. We never use it -- see
    #: `SocialPost.scheduled_at` -- but the UI may want to say so.
    native_scheduling: bool = False


class SocialProvider(ABC):
    """Implemented once per integration; selected by ``SocialAccount.provider``."""

    #: Registry key. Must match `SocialAccount.provider`.
    key: str = ""
    #: Platforms this implementation can publish to.
    platforms: tuple[str, ...] = ()

    def __init__(self, account=None):
        self.account = account

    # -- account lifecycle ---------------------------------------------

    @abstractmethod
    def begin_authorization(self, *, site, platform: str, redirect_uri: str) -> AuthorizationStart:
        """Return where to send the user to grant access."""

    @abstractmethod
    def complete_authorization(self, *, site, platform: str, payload: dict) -> AccountInfo:
        """Exchange the callback payload for a usable credential."""

    def refresh_credentials(self) -> AccountInfo | None:
        """Refresh an expiring token. Return None when unsupported."""
        return None

    # -- publishing -----------------------------------------------------

    def validate(self, *, platform: str, caption: str, media: list) -> list[str]:
        """Return human-readable problems, or an empty list.

        The default implementation checks the shared `constraints` table, so a
        provider only overrides this for a rule that table cannot express.
        """
        from ..constraints import counted_length, spec_for

        spec = spec_for(platform)
        problems = []

        length = counted_length(caption, platform)
        if length > spec.max_length:
            problems.append(
                f"{spec.label}: {length - spec.max_length} characters over the "
                f"{spec.max_length} limit."
            )

        images = [m for m in media if str(m.get("mime", "")).startswith("image/")]
        videos = [m for m in media if str(m.get("mime", "")).startswith("video/")]
        if len(images) > spec.max_images:
            problems.append(f"{spec.label}: at most {spec.max_images} images.")
        if len(videos) > spec.max_videos:
            problems.append(f"{spec.label}: at most {spec.max_videos} videos.")

        for item in media:
            mime = str(item.get("mime", ""))
            size = int(item.get("bytes") or 0)
            name = item.get("alt") or item.get("url", "media")
            if mime.startswith("image/"):
                if mime not in spec.image_mimes:
                    problems.append(f"{spec.label}: {mime} images are not accepted.")
                elif size > spec.max_image_bytes:
                    problems.append(
                        f"{spec.label}: “{name}” is "
                        f"{size // (1024 * 1024)}MB, over the "
                        f"{spec.max_image_bytes // (1024 * 1024)}MB limit."
                    )
            elif mime.startswith("video/"):
                if mime not in spec.video_mimes:
                    problems.append(f"{spec.label}: {mime} video is not accepted.")
                elif size > spec.max_video_bytes:
                    problems.append(
                        f"{spec.label}: “{name}” is over the "
                        f"{spec.max_video_bytes // (1024 * 1024)}MB video limit."
                    )
        return problems

    def upload_media(self, *, platform: str, media: list) -> list:
        """Hand media to the platform, returning whatever `publish` needs."""
        return media

    @abstractmethod
    def publish(
        self, *, platform: str, caption: str, media: list, idempotency_key: str, state: dict
    ) -> PublishResult:
        """Publish, or raise ProviderError / ProviderNotReady."""

    def delete(self, *, external_id: str) -> bool:
        raise NotImplementedError(f"{self.key} cannot delete published posts.")

    def fetch_metrics(self, *, external_id: str) -> dict:
        return {}

    def capabilities(self) -> Capabilities:
        return Capabilities()
