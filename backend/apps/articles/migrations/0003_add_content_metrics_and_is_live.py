"""Add derived content metrics and the ``is_live`` visibility flag.

``is_live`` separates "is the article publicly visible" from ``published_at``,
which records first publication and must never be cleared. The data migration
backfills both the flag and the text metrics for existing rows so they are not
left at their column defaults.
"""

import hashlib
import json
import math

from django.db import migrations, models


def backfill(apps, schema_editor):
    from common.blocks import blocks_to_plaintext

    Article = apps.get_model("articles", "Article")
    updated = []
    # iterator() keeps memory flat on large tables; only the fields we touch are
    # loaded and written back.
    for article in Article.objects.only(
        "id", "content", "status"
    ).iterator(chunk_size=500):
        plain = blocks_to_plaintext(article.content)
        article.plain_text = plain
        article.word_count = len(plain.split())
        article.reading_time = max(1, math.ceil(article.word_count / 200))
        article.is_live = article.status == "published"
        article.content_hash = hashlib.sha256(
            json.dumps(article.content or {}, sort_keys=True, ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        updated.append(article)
        if len(updated) >= 500:
            Article.objects.bulk_update(
                updated,
                ["plain_text", "word_count", "reading_time", "is_live", "content_hash"],
            )
            updated = []
    if updated:
        Article.objects.bulk_update(
            updated,
            ["plain_text", "word_count", "reading_time", "is_live", "content_hash"],
        )


def noop(apps, schema_editor):
    """Reverse is a no-op: the columns are dropped by the AddField reversal."""


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0002_alter_article_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='content_hash',
            field=models.CharField(blank=True, default='', help_text='sha256 of the content JSON; drives optimistic concurrency.', max_length=64),
        ),
        migrations.AddField(
            model_name='article',
            name='is_live',
            field=models.BooleanField(db_index=True, default=False, help_text='Whether the article is currently visible to the public.'),
        ),
        migrations.AddField(
            model_name='article',
            name='plain_text',
            field=models.TextField(blank=True, default='', help_text='Flattened block text, including annotation bodies.'),
        ),
        migrations.AddField(
            model_name='article',
            name='word_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill, noop),
    ]
