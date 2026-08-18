"""Sitemap sharding.

Sharding is done here rather than in Next.js because only the backend knows the
full live set for a tenant. 5000 URLs per shard sits far below the 50k/50MB
protocol limit while keeping each shard small enough to regenerate cheaply.
"""

from __future__ import annotations

from apps.syndication.models import Placement

SHARD_SIZE = 5000


def live_placements(site):
    return (
        Placement.objects.live()
        .for_site(site)
        .select_related("article", "site")
        .order_by("-published_at", "id")
    )


def shard_index(site) -> list[dict]:
    """Describe each shard: number, entry count, and newest lastmod."""
    queryset = live_placements(site)
    total = queryset.count()
    if total == 0:
        return []

    shards = []
    for index in range((total + SHARD_SIZE - 1) // SHARD_SIZE):
        window = queryset[index * SHARD_SIZE : (index + 1) * SHARD_SIZE]
        newest = max(
            (p.article.updated_at for p in window if p.article.updated_at),
            default=None,
        )
        shards.append(
            {
                "n": index,
                "count": len(window),
                "lastmod": newest.isoformat() if newest else None,
            }
        )
    return shards


def shard_entries(site, index: int) -> list[dict]:
    """Sitemap entries for one shard, with per-placement SEO applied."""
    from apps.seo.resolver import resolve_seo

    window = live_placements(site)[index * SHARD_SIZE : (index + 1) * SHARD_SIZE]

    entries = []
    for placement in window:
        seo = resolve_seo(placement.article, site=site, placement=placement)
        # An editor can exclude a page without unpublishing it.
        if seo.hide_from_sitemap or not seo.robots_index:
            continue
        entries.append(
            {
                "url": placement.url,
                "lastmod": (
                    placement.article.updated_at.isoformat()
                    if placement.article.updated_at
                    else None
                ),
                "changefreq": seo.sitemap_changefreq,
                "priority": seo.sitemap_priority,
                "image": seo.og_image or None,
            }
        )
    return entries
