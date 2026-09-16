"""Rename the original platform identity without changing tenant URLs or slugs."""

from django.db import migrations


def rename_brand(apps, schema_editor, old, new, old_image, new_image):
    Site = apps.get_model("tenancy", "Site")
    SiteSettings = apps.get_model("tenancy", "SiteSettings")
    database = schema_editor.connection.alias
    sites = Site.objects.using(database).filter(name=old)
    if old == "Interactive Articles":
        sites = sites.filter(is_default=True)
    for site in sites:
        Site.objects.using(database).filter(pk=site.pk).update(name=new)
        settings = SiteSettings.objects.using(database).filter(site_id=site.pk).first()
        if settings is None:
            continue
        updates = {}
        for field in ("site_title", "title_template", "default_meta_description"):
            value = getattr(settings, field)
            if old in value:
                updates[field] = value.replace(old, new)
        if settings.default_og_image.endswith(old_image):
            updates["default_og_image"] = settings.default_og_image[:-len(old_image)] + new_image
        organization = dict(settings.organization_jsonld or {})
        for field in ("name", "legalName", "alternateName", "description"):
            if isinstance(organization.get(field), str):
                organization[field] = organization[field].replace(old, new)
        if organization != settings.organization_jsonld:
            updates["organization_jsonld"] = organization
        if updates:
            SiteSettings.objects.using(database).filter(pk=settings.pk).update(**updates)


def forwards(apps, schema_editor):
    rename_brand(apps, schema_editor, "Interactive Articles", "Storyloom", "/og/platform.jpg", "/og/storyloom.png")
    rename_brand(apps, schema_editor, "Spandor", "Storyloom", "/og/platform.jpg", "/og/storyloom.png")


def backwards(apps, schema_editor):
    rename_brand(apps, schema_editor, "Storyloom", "Spandor", "/og/storyloom.png", "/og/platform.jpg")


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0003_bootstrap_site_api_key")]
    operations = [migrations.RunPython(forwards, backwards)]
