"""Give SubCategory its own tenant column.

It could be reached via ``category__site``, but a direct FK means every tenant
table scopes identically (one filter, no join) and the SQL-level scoping test
can enforce it uniformly. ``SubCategory.save()`` derives the value from the
parent, so the denormalisation cannot drift.

Same nullable -> backfill -> NOT NULL sequence as the other content apps.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_site(apps, schema_editor):
    SubCategory = apps.get_model("categories", "SubCategory")
    # Inherit each row's tenant from its parent category. Done with a
    # correlated UPDATE rather than a Python loop so it stays one statement.
    from django.db.models import OuterRef, Subquery

    Category = apps.get_model("categories", "Category")
    SubCategory.objects.filter(site__isnull=True).update(
        site_id=Subquery(
            Category.objects.filter(pk=OuterRef("category_id")).values("site_id")[:1]
        )
    )


def noop(apps, schema_editor):
    """Reverse is handled by dropping the column."""


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0003_add_site"),
    ]

    operations = [
        migrations.AddField(
            model_name="subcategory",
            name="site",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
        migrations.RunPython(backfill_site, noop),
        migrations.AlterField(
            model_name="subcategory",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
    ]
