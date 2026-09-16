"""Content-version cache invalidation.

Enumerate-and-delete invalidation needs ``SCAN`` over the keyspace, which is
O(N) and races concurrent writers. Instead every cache key for a site embeds
that site's *content version*, and publishing bumps the version:

    pub:{site}:{version}:articles:{query_hash}

After ``bump_content_version(site)`` the old keys are simply unreachable and
age out under Redis' LRU. Mass invalidation becomes one atomic ``INCR``.

Every helper is written to survive Redis being unavailable -- the cache is
configured with ``IGNORE_EXCEPTIONS``, so a failed read returns ``None`` and
callers fall through to the database.
"""

from __future__ import annotations

import hashlib
import json

from django.core.cache import cache

CONTENT_VERSION_TTL = None  # never expires; only ever incremented
DEFAULT_PAGE_TTL = 300


def _version_key(site_id: int) -> str:
    return f"site:{site_id}:cv"


def get_content_version(site_id: int) -> int:
    """Current content version for a site, defaulting to 1."""
    if not site_id:
        return 0
    version = cache.get(_version_key(site_id))
    if version is None:
        cache.set(_version_key(site_id), 1, CONTENT_VERSION_TTL)
        return 1
    return int(version)


def bump_content_version(site_id: int) -> int:
    """Invalidate every cached response for a site."""
    if not site_id:
        return 0
    key = _version_key(site_id)
    try:
        return int(cache.incr(key))
    except ValueError:
        # Key absent (evicted, or first ever write): start a fresh generation.
        cache.set(key, 2, CONTENT_VERSION_TTL)
        return 2


def query_hash(**parts) -> str:
    """Stable short hash of query parameters, for use in a cache key."""
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def public_cache_key(site_id: int, kind: str, suffix: str = "") -> str:
    version = get_content_version(site_id)
    key = f"pub:{site_id}:{version}:{kind}"
    return f"{key}:{suffix}" if suffix else key


def etag_for(site_id: int, suffix: str = "") -> str:
    """Weak ETag tied to the site's content version."""
    return f'W/"{get_content_version(site_id)}-{suffix}"' if suffix else (
        f'W/"{get_content_version(site_id)}"'
    )
