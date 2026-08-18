"""Install CMS_SITE_API_KEY on the default site, if the env var is set.

The public delivery API requires a hashed key in ``tenancy_apikey``. The
frontend is given the raw value via ``CMS_SITE_API_KEY``, but nothing was
writing the matching hash on a fresh database -- every public request then
came back 403 "A valid X-API-Key header is required."
"""

import hashlib
import os

from django.db import migrations

API_KEY_PREFIX_LENGTH = 12
DEFAULT_SCOPES = ["read:content", "read:taxonomy", "read:media", "write:events"]


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def install_env_api_key(apps, schema_editor):
    Site = apps.get_model("tenancy", "Site")
    ApiKey = apps.get_model("tenancy", "ApiKey")

    raw_key = os.environ.get("CMS_SITE_API_KEY", "").strip()
    if not raw_key or len(raw_key) <= API_KEY_PREFIX_LENGTH:
        return

    site = Site.objects.filter(is_default=True).first()
    if site is None:
        return

    prefix = raw_key[:API_KEY_PREFIX_LENGTH]
    if ApiKey.objects.filter(prefix=prefix).exists():
        return

    ApiKey.objects.create(
        site=site,
        name="Frontend delivery",
        prefix=prefix,
        hashed_key=_hash_key(raw_key),
        scopes=DEFAULT_SCOPES,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_bootstrap_default_site"),
    ]

    operations = [
        migrations.RunPython(install_env_api_key, migrations.RunPython.noop),
    ]
