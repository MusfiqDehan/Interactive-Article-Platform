"""Attach articles to their owning tenant.

Same nullable -> backfill -> NOT NULL sequence as categories; see
``categories.0003_add_site`` for why it is not collapsed.

``Article.slug`` stays globally unique. Per-site URLs are expressed by
``syndication.Placement.path_slug``, so the article's own slug is an internal
identifier and does not need to vary by tenant.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_site(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    Site = apps.get_model("tenancy", "Site")

    site = Site.objects.filter(is_default=True).first()
    if site is None:
        if Article.objects.exists():
            raise RuntimeError(
                "No default Site exists; tenancy.0002_bootstrap_default_site "
                "must run before this migration."
            )
        return
    Article.objects.filter(site__isnull=True).update(site=site)


def noop(apps, schema_editor):
    """Reverse is handled by dropping the column."""


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0003_add_content_metrics_and_is_live"),
        ("tenancy", "0002_bootstrap_default_site"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
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
            model_name="article",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
    ]
