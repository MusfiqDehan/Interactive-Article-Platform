"""Move ``Article.subcategory`` into ``Article.category``, then drop the field.

An article used to record two things -- a category and, optionally, a
subcategory -- because the taxonomy was two flat levels. It is a tree now, so
one FK expresses the same fact and more: an article can sit at any depth.

The data step points ``category`` at the tree node the subcategory mirrors, so
"NMT is under Technology › Machine Learning" survives the change. Articles with
no subcategory keep the category they already had. **Nothing is discarded** --
this is a promotion, not a truncation, which is why it can run before the
column is removed rather than needing a backup of it.

The reverse is honest about its limits: it restores the ``subcategory`` column
and re-derives it from the tree wherever the article sits on a depth-1 node.
"""

from django.db import migrations


def promote_subcategory(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    SubCategory = apps.get_model("categories", "SubCategory")

    mirrors = {
        sub.pk: sub.mirror_of_id
        for sub in SubCategory.objects.exclude(mirror_of=None).only("id", "mirror_of")
    }
    for article in Article.objects.exclude(subcategory=None).only("id", "subcategory"):
        node_id = mirrors.get(article.subcategory_id)
        if node_id:
            Article.objects.filter(pk=article.pk).update(category_id=node_id)


def demote_to_subcategory(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    SubCategory = apps.get_model("categories", "SubCategory")

    by_node = {
        sub.mirror_of_id: sub.pk
        for sub in SubCategory.objects.exclude(mirror_of=None).only("id", "mirror_of")
    }
    for article in Article.objects.exclude(category=None).select_related("category"):
        sub_id = by_node.get(article.category_id)
        if sub_id:
            Article.objects.filter(pk=article.pk).update(
                subcategory_id=sub_id, category_id=article.category.parent_id
            )


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0006_backfill_last_published_at"),
        ("categories", "0006_build_category_tree"),
    ]

    operations = [
        migrations.RunPython(promote_subcategory, demote_to_subcategory),
        migrations.RemoveField(model_name="article", name="subcategory"),
    ]
