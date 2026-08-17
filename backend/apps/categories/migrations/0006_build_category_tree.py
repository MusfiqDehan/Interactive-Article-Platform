"""Turn the flat category list into a tree, and demote SubCategory to a mirror.

Two steps, both idempotent:

1. Every existing category becomes a root: ``path`` = its own padded pk,
   ``url_path`` = its slug, ``depth`` = 0.
2. Every ``SubCategory`` gains a depth-1 ``Category`` and points at it through
   ``mirror_of``. The subcategory row itself is left in place and untouched
   otherwise, so ``Article.subcategory`` FKs and the frozen ``/api/categories/``
   response stay exactly as they were.

Uses ``apps.get_model`` throughout: the imported models carry a ``save()`` that
generates slugs and rebuilds subtrees, which is the *current* behaviour and not
necessarily what the schema looked like at this point in history.
"""

from django.db import migrations

SEGMENT_WIDTH = 10


def build_tree(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    SubCategory = apps.get_model("categories", "SubCategory")

    # -- 1. existing categories become roots ----------------------------
    for category in Category.objects.all().iterator():
        Category.objects.filter(pk=category.pk).update(
            path=str(category.pk).zfill(SEGMENT_WIDTH),
            url_path=category.slug,
            depth=0,
            parent=None,
        )

    # -- 2. each subcategory gains a tree node --------------------------
    for sub in SubCategory.objects.select_related("category").order_by("pk").iterator():
        if sub.mirror_of_id:
            continue
        parent = sub.category

        # (site, name) and (site, slug) are unique on Category, and a
        # subcategory name may well collide with a root category on the same
        # site ("Tools" under two parents, or a subcategory sharing a root's
        # name). Suffix with the parent's slug, which is unique per site, so
        # the collision resolves deterministically rather than aborting the
        # migration halfway through.
        name, slug = sub.name, sub.slug or str(sub.pk)
        if Category.objects.filter(site_id=sub.site_id, name=name).exists():
            name = f"{sub.name} ({parent.name})"
        if Category.objects.filter(site_id=sub.site_id, slug=slug).exists():
            slug = f"{parent.slug}-{slug}"

        node = Category.objects.create(
            site_id=sub.site_id,
            parent=parent,
            name=name[:200],
            slug=slug[:200],
            description=sub.description,
            is_active=sub.is_active,
            order=sub.order,
            depth=1,
            path=f"{str(parent.pk).zfill(SEGMENT_WIDTH)}.",  # fixed up below
            url_path=f"{parent.slug}/{slug}"[:800],
        )
        Category.objects.filter(pk=node.pk).update(
            path=f"{str(parent.pk).zfill(SEGMENT_WIDTH)}.{str(node.pk).zfill(SEGMENT_WIDTH)}"
        )
        SubCategory.objects.filter(pk=sub.pk).update(mirror_of=node)


def unbuild_tree(apps, schema_editor):
    """Drop the generated tree nodes; the subcategory rows are already intact."""
    Category = apps.get_model("categories", "Category")
    SubCategory = apps.get_model("categories", "SubCategory")

    mirrored = list(
        SubCategory.objects.exclude(mirror_of=None).values_list("mirror_of_id", flat=True)
    )
    SubCategory.objects.exclude(mirror_of=None).update(mirror_of=None)
    Category.objects.filter(pk__in=mirrored).delete()
    Category.objects.all().update(path="", url_path="", depth=0, parent=None)


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0005_category_depth_category_parent_category_path_and_more"),
    ]

    operations = [migrations.RunPython(build_tree, unbuild_tree)]
