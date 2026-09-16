"""Sitemap sharding.

Sharding is done here rather than in Next.js because only the backend knows the
full live set for a tenant. 5000 URLs per shard sits far below the 50k/50MB
protocol limit while keeping each shard small enough to regenerate cheaply.
"""

from __future__ import annotations

from django.utils import timezone

from apps.syndication.models import Placement

SHARD_SIZE = 5000

# Static public surfaces. Search is omitted on purpose: query URLs are
# thin-content traps and robots.txt already noindexes them.
STATIC_PAGES = (
    {"path": "", "changefreq": "weekly", "priority": 1.0},
    {"path": "home", "changefreq": "daily", "priority": 0.9},
    {"path": "articles", "changefreq": "hourly", "priority": 0.8},
    {"path": "categories", "changefreq": "daily", "priority": 0.6},
    {"path": "llms.txt", "changefreq": "weekly", "priority": 0.3},
)


def live_placements(site):
    return (
        Placement.objects.live()
        .for_site(site)
        .select_related("article", "site")
        .order_by("-published_at", "id")
    )


def _static_entries(site) -> list[dict]:
    now = timezone.now().isoformat()
    og = ""
    try:
        og = site.settings.default_og_image or ""
    except Exception:
        og = ""
    entries = []
    for page in STATIC_PAGES:
        entries.append(
            {
                "url": site.url_for(page["path"]),
                "lastmod": now,
                "changefreq": page["changefreq"],
                "priority": page["priority"],
                "image": og or None,
            }
        )
    return entries


def _category_entries(site) -> list[dict]:
    from apps.categories.models import Category

    rows = (
        Category.unscoped.filter(site=site, is_active=True)
        .only("slug", "updated_at")
        .order_by("order", "name")
    )
    return [
        {
            "url": site.url_for(f"categories/{row.slug}"),
            "lastmod": row.updated_at.isoformat() if row.updated_at else None,
            "changefreq": "weekly",
            "priority": 0.5,
            "image": None,
        }
        for row in rows
    ]


def extras_count(site) -> int:
    from apps.categories.models import Category

    return len(STATIC_PAGES) + Category.unscoped.filter(
        site=site, is_active=True
    ).count()


def shard_index(site) -> list[dict]:
    """Describe each shard: number, entry count, and newest lastmod.

    Uses COUNT plus one-row windows rather than materialising every placement
    just to compute the index. At thousands of articles the old slice-of-5000
    loop was a full table walk on every sitemap request.

    Shard 0 always exists so the homepage, publication landing, and category
    index remain discoverable even before the first article is published.
    """
    queryset = live_placements(site)
    total = queryset.count()
    extra = extras_count(site)
    if total == 0:
        return [{"n": 0, "count": extra, "lastmod": timezone.now().isoformat()}]

    shards = []
    shard_count = (total + SHARD_SIZE - 1) // SHARD_SIZE
    for index in range(shard_count):
        offset = index * SHARD_SIZE
        newest = (
            queryset[offset : offset + 1]
            .values_list("article__updated_at", flat=True)
            .first()
        )
        count = min(SHARD_SIZE, total - offset)
        if index == 0:
            count += extra
        shards.append(
            {
                "n": index,
                "count": count,
                "lastmod": newest.isoformat() if newest else None,
            }
        )
    return shards


def shard_entries(site, index: int) -> list[dict]:
    """Sitemap entries for one shard, with per-placement SEO applied."""
    from apps.seo.resolver import resolve_seo

    extras = _static_entries(site) + _category_entries(site) if index == 0 else []
    window = live_placements(site)[index * SHARD_SIZE : (index + 1) * SHARD_SIZE]

    entries = list(extras)
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
