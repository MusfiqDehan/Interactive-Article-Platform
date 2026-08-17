from django.db import migrations, models


def backfill(apps, schema_editor):
    """Seed last_published_at from published_at for existing content.

    Without this every pre-existing article reports "never published" in the
    studio despite being live, because last_published_at only starts being
    written by transitions from now on. Copying published_at is the correct
    value: for an article that has been published exactly once, first and most
    recent publication are the same moment.
    """
    # get_model, never the imported class: the historical model is the only one
    # guaranteed to match the schema at this point in the migration graph.
    Article = apps.get_model("articles", "Article")
    Article.objects.filter(
        published_at__isnull=False, last_published_at__isnull=True
    ).update(last_published_at=models.F("published_at"))


def noop(apps, schema_editor):
    """Deliberately not reversed: clearing the column would destroy values
    written by real publishes after this migration ran."""


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0005_article_last_published_at_article_locale_and_more"),
    ]

    operations = [migrations.RunPython(backfill, noop)]
