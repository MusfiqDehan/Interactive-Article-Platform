"""Keep the index in step with articles.

``post_save`` → ``transaction.on_commit`` → Celery task. Never a signal doing
HTTP directly: that would put a network call inside the transaction that saves
an article, so a slow Meilisearch would slow every save and an unreachable one
would roll back a publish. Deferring to commit also means an article that is
never actually committed is never indexed.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.articles.models import Article


@receiver(post_save, sender=Article, dispatch_uid="search.index_article")
def index_on_save(sender, instance: Article, **kwargs):
    from .tasks import index_article

    article_id = instance.pk
    transaction.on_commit(lambda: index_article.delay(article_id))


@receiver(post_delete, sender=Article, dispatch_uid="search.remove_article")
def remove_on_delete(sender, instance: Article, **kwargs):
    from .tasks import remove_article

    site_id, article_id = instance.site_id, instance.pk
    # Not deferred to commit: the row is already gone from this transaction's
    # view, and if it rolls back the worst case is one re-index, which the
    # drift repair would have done anyway.
    transaction.on_commit(lambda: remove_article.delay(site_id, article_id))
