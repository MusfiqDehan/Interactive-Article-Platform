"""Keep the primary placement in step with its article.

An article's own site always has a placement, and that placement's visibility
mirrors ``Article.is_live``. Doing this with a signal (rather than in
``Article.save``) keeps the articles app unaware of syndication, so the legacy
code path is untouched.

Syndicated (non-primary) placements are deliberately NOT auto-published here --
distributing to another site is an editorial decision, made in the studio.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.articles.models import Article

from .models import Placement


@receiver(post_save, sender=Article, dispatch_uid="syndication_sync_primary_placement")
def sync_primary_placement(sender, instance, created, **kwargs):
    placement = Placement.objects.filter(article=instance, is_primary=True).first()

    if placement is None:
        Placement.objects.update_or_create(
            article=instance,
            site_id=instance.site_id,
            defaults={
                "is_primary": True,
                "is_live": instance.is_live,
                "canonical_to_primary": False,
                "published_at": instance.published_at,
                "path_slug": instance.slug,
            },
        )
        return

    updates = {}
    if placement.is_live != instance.is_live:
        updates["is_live"] = instance.is_live
    if placement.published_at != instance.published_at:
        updates["published_at"] = instance.published_at
    # The article slug is the primary placement's path unless an editor has
    # deliberately diverged it.
    if placement.path_slug != instance.slug and placement.path_slug == "":
        updates["path_slug"] = instance.slug

    if updates:
        Placement.objects.filter(pk=placement.pk).update(**updates)
