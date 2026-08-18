"""Resolve the effective SEO metadata for an object on a given site.

Three levels, most specific first:

    1. the per-site ``SEOMetadata`` row  (an editor's explicit override)
    2. the default row (``site IS NULL``)
    3. values computed from the content itself

Level 3 matters as much as the others: most articles will never have an
explicit SEO row, and they still need a sensible title, description, OG image
and canonical. An empty string at levels 1-2 falls through -- a blank override
means "not set", not "deliberately empty".

The single highest-leverage rule lives in ``_canonical``: a syndicated
placement points its canonical back at the owning site, so the same article on
five partner sites does not compete with itself in search results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType

from .models import SEOMetadata

# Google truncates around these lengths; used for computed fallbacks.
META_DESCRIPTION_LENGTH = 155
HEADLINE_MAX = 110


@dataclass
class ResolvedSEO:
    meta_title: str = ""
    meta_description: str = ""
    canonical_url: str = ""
    focus_keyword: str = ""
    secondary_keywords: list = field(default_factory=list)

    robots_index: bool = True
    robots_follow: bool = True
    robots_noarchive: bool = False
    robots_nosnippet: bool = False
    robots_noimageindex: bool = False
    max_snippet: int = -1
    max_image_preview: str = "large"
    max_video_preview: int = -1
    unavailable_after: str | None = None

    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_image_alt: str = ""
    og_type: str = "article"
    og_locale: str = ""

    twitter_card: str = "summary_large_image"
    twitter_title: str = ""
    twitter_description: str = ""
    twitter_image: str = ""
    twitter_site: str = ""

    schema_type: str = "Article"
    structured_data_overrides: dict = field(default_factory=dict)
    faq_items: list = field(default_factory=list)
    hide_from_sitemap: bool = False
    sitemap_priority: float = 0.7
    sitemap_changefreq: str = "weekly"

    def as_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


def _rows_for(obj, site):
    """Return ``(site_row, default_row)`` in a single query."""
    content_type = ContentType.objects.get_for_model(type(obj))
    rows = SEOMetadata.objects.filter(content_type=content_type, object_id=obj.pk)
    site_row = default_row = None
    for row in rows:
        if row.site_id is None:
            default_row = row
        elif site is not None and row.site_id == site.pk:
            site_row = row
    return site_row, default_row


def _pick(attr, site_row, default_row, computed=""):
    """First non-empty value across the three levels."""
    for row in (site_row, default_row):
        if row is None:
            continue
        value = getattr(row, attr, None)
        # Empty string / empty list means "unset", not "deliberately blank".
        if value not in (None, "", [], {}):
            return value
    return computed


def _pick_bool(attr, site_row, default_row, computed):
    """Booleans need identity, not truthiness -- False is a real setting."""
    for row in (site_row, default_row):
        if row is not None:
            return getattr(row, attr)
    return computed


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:")
    return f"{cut}…"


def _canonical(article, site, placement, site_row, default_row) -> str:
    explicit = _pick("canonical_url", site_row, default_row)
    if explicit:
        return explicit
    if placement is not None:
        # THE duplicate-content lever: a syndicated copy points home.
        return placement.resolved_canonical()
    if site is not None:
        return site.url_for(f"articles/{article.slug}")
    return ""


def resolve_seo(obj, site=None, placement=None) -> ResolvedSEO:
    """Resolve effective SEO for ``obj`` as rendered on ``site``."""
    site_row, default_row = _rows_for(obj, site)

    site_settings = None
    if site is not None:
        site_settings = getattr(site, "settings", None)

    title = getattr(obj, "title", "") or getattr(obj, "name", "")
    excerpt = (getattr(obj, "excerpt", "") or "").strip()
    plain_text = (getattr(obj, "plain_text", "") or "").strip()

    if placement is not None:
        title = placement.override_title or title
        excerpt = placement.override_excerpt or excerpt

    # Description: explicit -> excerpt -> opening of the body -> site default.
    computed_description = excerpt or _truncate(plain_text, META_DESCRIPTION_LENGTH)
    if not computed_description and site_settings is not None:
        computed_description = site_settings.default_meta_description

    computed_image = getattr(obj, "featured_image", "") or ""
    if not computed_image and site_settings is not None:
        computed_image = site_settings.default_og_image

    meta_title = _pick("meta_title", site_row, default_row, title)
    meta_description = _pick(
        "meta_description", site_row, default_row, computed_description
    )
    og_image = _pick("og_image", site_row, default_row, computed_image)

    return ResolvedSEO(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=_canonical(obj, site, placement, site_row, default_row),
        focus_keyword=_pick("focus_keyword", site_row, default_row),
        secondary_keywords=_pick("secondary_keywords", site_row, default_row, []),
        robots_index=_pick_bool("robots_index", site_row, default_row, True),
        robots_follow=_pick_bool("robots_follow", site_row, default_row, True),
        robots_noarchive=_pick_bool("robots_noarchive", site_row, default_row, False),
        robots_nosnippet=_pick_bool("robots_nosnippet", site_row, default_row, False),
        robots_noimageindex=_pick_bool(
            "robots_noimageindex", site_row, default_row, False
        ),
        max_snippet=_pick("max_snippet", site_row, default_row, -1),
        max_image_preview=_pick("max_image_preview", site_row, default_row, "large"),
        max_video_preview=_pick("max_video_preview", site_row, default_row, -1),
        unavailable_after=(
            value.isoformat()
            if (value := _pick("unavailable_after", site_row, default_row, None))
            else None
        ),
        # Social fields inherit from the meta fields when unset, so sharing a
        # page never produces an empty card.
        og_title=_pick("og_title", site_row, default_row, meta_title),
        og_description=_pick("og_description", site_row, default_row, meta_description),
        og_image=og_image,
        og_image_alt=_pick("og_image_alt", site_row, default_row, meta_title),
        og_type=_pick("og_type", site_row, default_row, "article"),
        og_locale=_pick(
            "og_locale", site_row, default_row, site.locale if site else ""
        ),
        twitter_card=_pick(
            "twitter_card", site_row, default_row, "summary_large_image"
        ),
        twitter_title=_pick("twitter_title", site_row, default_row, meta_title),
        twitter_description=_pick(
            "twitter_description", site_row, default_row, meta_description
        ),
        twitter_image=_pick("twitter_image", site_row, default_row, og_image),
        twitter_site=_pick("twitter_site", site_row, default_row),
        schema_type=_pick("schema_type", site_row, default_row, "Article"),
        structured_data_overrides=_pick(
            "structured_data_overrides", site_row, default_row, {}
        ),
        faq_items=_pick("faq_items", site_row, default_row, []),
        hide_from_sitemap=_pick_bool(
            "hide_from_sitemap", site_row, default_row, False
        ),
        sitemap_priority=float(_pick("sitemap_priority", site_row, default_row, 0.7)),
        sitemap_changefreq=_pick(
            "sitemap_changefreq", site_row, default_row, "weekly"
        ),
    )
