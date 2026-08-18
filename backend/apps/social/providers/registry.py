"""Provider registry.

The only place that maps ``SocialAccount.provider`` to a class. Everything
else asks for a provider by account and gets back something implementing
``SocialProvider``, which is what makes swapping an implementation a data
change rather than a code change.
"""

from __future__ import annotations

from .base import SocialProvider

_REGISTRY: dict[str, type[SocialProvider]] = {}


def register(cls: type[SocialProvider]) -> type[SocialProvider]:
    if not cls.key:
        raise ValueError(f"{cls.__name__} must define a `key`.")
    _REGISTRY[cls.key] = cls
    return cls


def get_provider(account) -> SocialProvider:
    """Instantiate the provider for an account."""
    cls = _REGISTRY.get(account.provider)
    if cls is None:
        raise LookupError(
            f"No provider registered under {account.provider!r}. "
            f"Known: {', '.join(sorted(_REGISTRY)) or 'none'}."
        )
    return cls(account=account)


def provider_for_key(key: str) -> type[SocialProvider]:
    cls = _REGISTRY.get(key)
    if cls is None:
        raise LookupError(f"No provider registered under {key!r}.")
    return cls


def providers_for_platform(platform: str) -> list[str]:
    return sorted(key for key, cls in _REGISTRY.items() if platform in cls.platforms)


def registered() -> dict[str, type[SocialProvider]]:
    return dict(_REGISTRY)
