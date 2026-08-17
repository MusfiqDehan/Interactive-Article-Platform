"""Drop the deprecated ``SubCategory`` mirror table.

By this point nothing reads it: the tree carries the structure, ``Article``
points at a tree node directly (``articles.0007``), and the legacy API that was
its only consumer is gone. The compatibility shim it existed for has served its
release.

Irreversible on purpose. Re-adding an empty table would satisfy the migration
graph and restore nothing, which is worse than saying so -- rolling back past
this point means restoring from a backup.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0006_build_category_tree"),
        # The FK from Article must be gone before the table can be.
        ("articles", "0007_article_category_from_tree"),
    ]

    operations = [
        migrations.RemoveField(model_name="subcategory", name="category"),
        migrations.RemoveField(model_name="subcategory", name="mirror_of"),
        migrations.RemoveField(model_name="subcategory", name="site"),
        migrations.DeleteModel(name="SubCategory"),
    ]
