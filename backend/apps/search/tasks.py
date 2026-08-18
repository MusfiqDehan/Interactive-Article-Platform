"""Indexing tasks and drift repair."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from common.locks import advisory_lock

from . import client
from .models import IndexingLog

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 10


@shared_task(name="search.index_article")
def index_article(article_id: int) -> dict:
    """Index one article, recording the outcome either way."""
    from apps.articles.models import Article

    article = (
        Article.unscoped.filter(pk=article_id)
        .select_related("author", "category", "site")
        .first()
    )
    if article is None:
        return {"article": article_id, "skipped": "gone"}

    log, _ = IndexingLog.unscoped.get_or_create(
        site_id=article.site_id, article_pk=article.pk, action="upsert"
    )

    # Drafts must not be searchable. A de-index rather than a skip: an article
    # unpublished after being indexed would otherwise stay findable.
    if not article.is_live:
        ok = client.remove(article.site_id, article.pk)
        log.mark(
            "indexed" if ok else "failed",
            "" if ok else "de-index failed",
            content_hash=article.content_hash,
        )
        return {"article": article_id, "removed": ok}

    ok = client.upsert(article)
    log.mark(
        "indexed" if ok else "failed",
        "" if ok else "index unavailable",
        content_hash=article.content_hash,
    )
    return {"article": article_id, "indexed": ok}


@shared_task(name="search.remove_article")
def remove_article(site_id: int, article_id: int) -> dict:
    ok = client.remove(site_id, article_id)
    log, _ = IndexingLog.unscoped.get_or_create(
        site_id=site_id, article_pk=article_id, action="delete"
    )
    log.mark("indexed" if ok else "failed", "" if ok else "delete failed")
    return {"article": article_id, "removed": ok}


@shared_task(name="search.repair_drift")
def repair_drift(limit: int = 200) -> dict:
    """Re-try failed indexing, and catch entries that went stale.

    Two kinds of drift, both real:

    * **Failed** -- Meilisearch was down when the publish fired.
    * **Stale** -- the index succeeded, then the article changed and the
      reindex was lost. Detected by comparing the article's ``content_hash``
      with the one recorded at index time, which is why the log stores it.
    """
    from apps.articles.models import Article

    with advisory_lock("search:repair", timeout=300) as acquired:
        if acquired is False:
            return {"skipped": "another worker is repairing"}

        if client.get_client() is None:
            return {"skipped": "search unavailable"}

        repaired = 0
        for log in IndexingLog.unscoped.filter(
            state="failed", attempts__lt=MAX_ATTEMPTS
        ).order_by("updated_at")[:limit]:
            index_article(log.article_pk)
            repaired += 1

        stale = 0
        indexed = {
            row["article_pk"]: row["content_hash"]
            for row in IndexingLog.unscoped.filter(
                state="indexed", action="upsert"
            ).values("article_pk", "content_hash")[: limit * 5]
        }
        if indexed:
            for article in Article.unscoped.filter(
                pk__in=indexed, is_live=True
            ).only("id", "content_hash")[:limit]:
                if indexed.get(article.pk) != article.content_hash:
                    index_article(article.pk)
                    stale += 1

        # Live articles that were never logged at all -- the index was created
        # after they were published, or the log row was lost.
        missing = 0
        unlogged = (
            Article.unscoped.filter(is_live=True)
            .exclude(pk__in=indexed)
            .only("id")[:limit]
        )
        for article in unlogged:
            index_article(article.pk)
            missing += 1

        return {"retried": repaired, "stale": stale, "unindexed": missing}


@shared_task(name="search.rebuild_index")
def rebuild_index(site_id: int) -> dict:
    """Rebuild a site's index with **zero downtime**, via a swap.

    Built into a scratch index and swapped in atomically, rather than cleared
    and refilled. Clearing first means every search between the clear and the
    last document returns nothing -- a rebuild that takes two minutes is two
    minutes of a site looking like it has no content.
    """
    from apps.articles.models import Article

    engine = client.get_client()
    if engine is None:
        return {"skipped": "search unavailable"}

    target = client.index_name(site_id)
    scratch = f"{target}_rebuild"

    try:
        engine.create_index(scratch, {"primaryKey": "id"})
        engine.index(scratch).update_settings(
            {
                "searchableAttributes": client.SEARCHABLE_ATTRIBUTES,
                "filterableAttributes": client.FILTERABLE_ATTRIBUTES,
                "sortableAttributes": client.SORTABLE_ATTRIBUTES,
                "rankingRules": client.RANKING_RULES,
            }
        )

        count = 0
        batch: list[dict] = []
        queryset = (
            Article.unscoped.filter(site_id=site_id, is_live=True)
            .select_related("author", "category", "site")
            .iterator(chunk_size=200)
        )
        for article in queryset:
            batch.append(client.document_for(article))
            if len(batch) >= 200:
                engine.index(scratch).add_documents(batch)
                count += len(batch)
                batch = []
        if batch:
            engine.index(scratch).add_documents(batch)
            count += len(batch)

        # The atomic moment. Searches before it hit the old index, after it the
        # new one; there is no window where either is empty.
        engine.swap_indexes([{"indexes": [target, scratch]}])
        engine.delete_index(scratch)

        IndexingLog.unscoped.filter(site_id=site_id).update(
            state="indexed", last_error="", updated_at=timezone.now()
        )
        return {"site": site_id, "documents": count}
    except Exception as exc:
        logger.exception("Rebuild failed for site %s", site_id)
        return {"site": site_id, "error": str(exc)}
