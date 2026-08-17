"""Attach categories to a tenant.

Three steps, deliberately not collapsed into one ``AddField(null=False)``:

  1. add the column as nullable  -- instant, no table rewrite
  2. backfill it                 -- the only slow part
  3. tighten it to NOT NULL      -- validates against already-correct data

Collapsing these would make PostgreSQL materialise a default for every row
inside the ALTER, and our "default" is a lookup, not a constant.

The unique index on ``slug``/``name`` also moves from global to per-site here.
Dropping the old index and adding the composite happen in the same migration
(and therefore the same transaction), so no window exists where a concurrent
insert could create a duplicate that then blocks index creation.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_site(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    Site = apps.get_model("tenancy", "Site")

    site = Site.objects.filter(is_default=True).first()
    if site is None:
        if Category.objects.exists():
            raise RuntimeError(
                "No default Site exists; tenancy.0002_bootstrap_default_site "
                "must run before this migration."
            )
        return
    Category.objects.filter(site__isnull=True).update(site=site)


def noop(apps, schema_editor):
    """Reverse is handled by dropping the column."""


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0002_alter_category_slug_alter_subcategory_slug"),
        # Guarantees the default Site row exists before the backfill runs.
        ("tenancy", "0002_bootstrap_default_site"),
    ]

    operations = [
        # -- step 1: nullable column
        migrations.AddField(
            model_name="category",
            name="site",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
        # -- step 2: backfill
        migrations.RunPython(backfill_site, noop),
        # -- step 3: enforce
        migrations.AlterField(
            model_name="category",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
        # -- global uniqueness -> per-site uniqueness
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(allow_unicode=True, blank=True, max_length=200),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("site", "slug"), name="category_unique_site_slug"
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("site", "name"), name="category_unique_site_name"
            ),
        ),
    ]
