"""Meilisearch: index settings, documents, and tenant tokens.

**Why Meilisearch over Typesense.** Its *tenant tokens* are signed JWTs that
carry a ``searchRules`` filter, so we can mint one per API key and let the
browser query Meilisearch **directly**. Every alternative puts Django on the
search path, which is the one place a proxy hop is most visible: search is
typed, so it fires per keystroke.

Two more reasons it fits this schema specifically: it is schemaless, and our
documents grow a field every time a block type is added; and its typo
tolerance handles mixed Bengali/Latin text, where an exact-match engine turns
one transliteration choice into zero results.

Every call here fails **soft**. Search being down must degrade search, never
publishing -- so an unreachable Meilisearch returns empty results and logs,
and the drift-repair task heals the index when it comes back.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

#: One index per site. Simpler than one shared index with a filter, and it
#: makes "delete a tenant" a single DELETE rather than a scan.
INDEX_PREFIX = "articles"

#: Ranked in the order the engine applies them. `published_at:desc` last so it
#: only breaks ties -- putting recency above relevance is how a search box
#: starts returning yesterday's unrelated post for every query.
RANKING_RULES = [
    "words",
    "typo",
    "proximity",
    "attribute",
    "sort",
    "exactness",
    "published_at:desc",
]

SEARCHABLE_ATTRIBUTES = [
    "title",
    "excerpt",
    # Annotation text is *in* plain_text (see common.blocks), which is what
    # makes a phrase that appears only inside an annotation findable at all.
    "plain_text",
    "tags",
    "category",
    "author",
]
FILTERABLE_ATTRIBUTES = ["site_id", "category", "tags", "locale", "is_live", "author"]
SORTABLE_ATTRIBUTES = ["published_at", "views_count", "word_count"]


def index_name(site_id: int) -> str:
    return f"{INDEX_PREFIX}_{site_id}"


def get_client():
    """The Meilisearch client, or None when it is not configured/reachable."""
    url = getattr(settings, "MEILISEARCH_URL", "")
    if not url:
        return None
    try:
        import meilisearch

        return meilisearch.Client(url, getattr(settings, "MEILISEARCH_MASTER_KEY", ""))
    except Exception:
        logger.warning("Meilisearch client unavailable", exc_info=True)
        return None


def ensure_index(site_id: int) -> bool:
    """Create the index and apply settings. Idempotent."""
    client = get_client()
    if client is None:
        return False
    try:
        name = index_name(site_id)
        client.create_index(name, {"primaryKey": "id"})
        index = client.index(name)
        index.update_settings(
            {
                "searchableAttributes": SEARCHABLE_ATTRIBUTES,
                "filterableAttributes": FILTERABLE_ATTRIBUTES,
                "sortableAttributes": SORTABLE_ATTRIBUTES,
                "rankingRules": RANKING_RULES,
                # Bengali has no stop-word list worth applying; leaving this
                # empty is deliberate rather than an omission.
                "stopWords": [],
                "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8}},
            }
        )
        return True
    except Exception:
        logger.warning("Could not ensure index for site %s", site_id, exc_info=True)
        return False


def document_for(article) -> dict[str, Any]:
    """The searchable shape of an article.

    ``plain_text`` already includes annotation prose, which is the whole point:
    a phrase that appears *only* inside an annotation has to be findable, and
    on this platform a large share of the substance lives there.
    """
    from apps.taxonomy.models import tags_for

    placement = article.placements.filter(is_primary=True).first()
    return {
        "id": article.pk,
        "site_id": article.site_id,
        "title": article.title,
        "slug": article.slug,
        "excerpt": article.excerpt,
        "plain_text": (article.plain_text or "")[:50_000],
        "category": article.category.name if article.category_id else "",
        "category_slug": article.category.slug if article.category_id else "",
        "tags": [tag.name for tag in tags_for(article)],
        "author": getattr(article.author, "username", "") if article.author_id else "",
        "locale": article.locale or "",
        "is_live": bool(article.is_live),
        "featured_image": article.featured_image,
        "reading_time": article.reading_time,
        "word_count": article.word_count,
        "views_count": article.views_count,
        "path_slug": placement.path_slug if placement else article.slug,
        "published_at": int(article.published_at.timestamp()) if article.published_at else 0,
    }


def upsert(article) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.index(index_name(article.site_id)).add_documents([document_for(article)])
        return True
    except Exception:
        logger.warning("Indexing failed for article %s", article.pk, exc_info=True)
        return False


def remove(site_id: int, article_id: int) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.index(index_name(site_id)).delete_document(article_id)
        return True
    except Exception:
        logger.warning("De-indexing failed for article %s", article_id, exc_info=True)
        return False


def search(site_id: int, query: str, *, limit: int = 20, offset: int = 0, filters=None):
    """Server-side search. Returns an empty result set when unavailable."""
    client = get_client()
    if client is None:
        return {"hits": [], "estimatedTotalHits": 0, "query": query, "available": False}
    try:
        result = client.index(index_name(site_id)).search(
            query,
            {
                "limit": limit,
                "offset": offset,
                # Non-negotiable: without it, a draft is one search away from
                # being public.
                "filter": " AND ".join(["is_live = true", *(filters or [])]),
                "attributesToHighlight": ["title", "excerpt", "plain_text"],
                "attributesToCrop": ["plain_text"],
                "cropLength": 40,
            },
        )
        result["available"] = True
        return result
    except Exception:
        logger.warning("Search failed for site %s", site_id, exc_info=True)
        return {"hits": [], "estimatedTotalHits": 0, "query": query, "available": False}


def tenant_token(site_id: int, *, expires_at=None) -> str:
    """A signed token scoped to one site's live content.

    This is what lets the browser talk to Meilisearch directly. The rules are
    baked into the signature, so a token cannot be edited to widen its scope --
    which is the only reason handing one to a client is safe.
    """
    client = get_client()
    if client is None:
        return ""
    try:
        return client.generate_tenant_token(
            api_key_uid=getattr(settings, "MEILISEARCH_SEARCH_KEY_UID", ""),
            search_rules={index_name(site_id): {"filter": "is_live = true"}},
            api_key=getattr(settings, "MEILISEARCH_SEARCH_KEY", ""),
            expires_at=expires_at,
        )
    except Exception:
        logger.warning("Could not mint a tenant token for site %s", site_id, exc_info=True)
        return ""
