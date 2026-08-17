"""Attach media files to a tenant.

Same nullable -> backfill -> NOT NULL sequence as the other content apps.

Media is referenced from article content by absolute URL, so cross-site reuse
needs no join table -- the ``site`` column records ownership for the library UI
and for quota/permission decisions, not for URL resolution.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_site(apps, schema_editor):
    MediaFile = apps.get_model("media_library", "MediaFile")
    Site = apps.get_model("tenancy", "Site")

    site = Site.objects.filter(is_default=True).first()
    if site is None:
        if MediaFile.objects.exists():
            raise RuntimeError(
                "No default Site exists; tenancy.0002_bootstrap_default_site "
                "must run before this migration."
            )
        return
    MediaFile.objects.filter(site__isnull=True).update(site=site)


def noop(apps, schema_editor):
    """Reverse is handled by dropping the column."""


class Migration(migrations.Migration):

    dependencies = [
        ("media_library", "0001_initial"),
        ("tenancy", "0002_bootstrap_default_site"),
    ]

    operations = [
        migrations.AddField(
            model_name="mediafile",
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
            model_name="mediafile",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="tenancy.site",
            ),
        ),
    ]
