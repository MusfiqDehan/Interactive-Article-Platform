"""Create the default Site every existing row will be attached to.

This must run before any ``add_site`` migration in the content apps, and those
migrations declare it as an explicit dependency -- otherwise a migrate against a
fresh database would try to backfill against an empty ``tenancy_site`` table.

Values come from the environment so a fresh deployment lands on its real domain
rather than a placeholder that then has to be corrected by hand.
"""

import os

from django.db import migrations

DEFAULT_SLUG = "default"


def _env(name, fallback):
    value = os.environ.get(name, "").strip()
    return value or fallback


def create_default_site(apps, schema_editor):
    # Historical models only: importing apps.tenancy.models directly would break
    # replaying this migration once the model gains new fields.
    Site = apps.get_model("tenancy", "Site")
    SiteSettings = apps.get_model("tenancy", "SiteSettings")

    if Site.objects.filter(is_default=True).exists():
        return

    allowed = _env("ALLOWED_HOSTS", "localhost")
    primary_domain = allowed.split(",")[0].strip().lower() or "localhost"
    if primary_domain in {"*", ""}:
        primary_domain = "localhost"

    base_url = _env("SITE_BASE_URL", "").rstrip("/")
    if not base_url:
        scheme = "http" if primary_domain in {"localhost", "127.0.0.1"} else "https"
        port = ":3003" if primary_domain in {"localhost", "127.0.0.1"} else ""
        base_url = f"{scheme}://{primary_domain}{port}"

    site = Site.objects.create(
        name=_env("SITE_NAME", "Interactive Articles"),
        slug=DEFAULT_SLUG,
        kind="owned",
        primary_domain=primary_domain,
        base_url=base_url,
        locale=_env("SITE_LOCALE", "en"),
        is_default=True,
        is_active=True,
    )
    SiteSettings.objects.create(
        site=site,
        site_title=site.name,
        title_template="%s | " + site.name,
    )


def remove_default_site(apps, schema_editor):
    Site = apps.get_model("tenancy", "Site")
    Site.objects.filter(slug=DEFAULT_SLUG, is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_site, remove_default_site),
    ]
