"""Give every existing article a primary placement on its owning site.

Without this, articles created before syndication existed would be invisible to
the public API, which resolves content through placements rather than through
``Article`` directly.

``path_slug`` starts equal to the article slug; ``is_live`` mirrors the
article's current visibility so nothing is silently published or unpublished by
the migration itself.
"""

from django.db import migrations


def create_primary_placements(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    Placement = apps.get_model("syndication", "Placement")

    existing = set(
        Placement.objects.filter(is_primary=True).values_list("article_id", flat=True)
    )

    batch = []
    for article in Article.objects.only(
        "id", "site_id", "slug", "status", "is_live", "published_at"
    ).iterator(chunk_size=500):
        if article.id in existing:
            continue
        batch.append(
            Placement(
                article_id=article.id,
                site_id=article.site_id,
                path_slug=article.slug,
                is_primary=True,
                is_live=bool(article.is_live),
                # The owning site is the canonical home, so it self-canonicalises.
                canonical_to_primary=False,
                published_at=article.published_at,
            )
        )
        if len(batch) >= 500:
            Placement.objects.bulk_create(batch, ignore_conflicts=True)
            batch = []

    if batch:
        Placement.objects.bulk_create(batch, ignore_conflicts=True)


def remove_primary_placements(apps, schema_editor):
    Placement = apps.get_model("syndication", "Placement")
    Placement.objects.filter(is_primary=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("syndication", "0001_initial"),
        # Articles must already carry a site before placements can reference it.
        ("articles", "0004_add_site"),
    ]

    operations = [
        migrations.RunPython(create_primary_placements, remove_primary_placements),
    ]
