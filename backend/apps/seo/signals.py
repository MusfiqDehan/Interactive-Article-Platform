"""Automatic 301s when a URL changes.

Renaming a published article silently breaks every existing inbound link and
every indexed URL. Catching the change here means an editor cannot forget: the
redirect is created as part of the same save.

Only *published* content generates redirects -- a draft's slug was never public,
so a redirect for it would be noise in the table (and in the front-end
middleware payload, which is loaded wholesale).
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.articles.models import Article

from .models import Redirect

# Stashes the previous slug between pre_save and post_save.
_PENDING: dict[int, str] = {}


@receiver(pre_save, sender=Article, dispatch_uid="seo_capture_slug_change")
def capture_slug_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = (
        Article.unscoped.filter(pk=instance.pk)
        .values_list("slug", "is_live")
        .first()
    )
    if not previous:
        return
    old_slug, was_live = previous
    # Only worth a redirect if the old URL was actually reachable.
    if old_slug and old_slug != instance.slug and was_live:
        _PENDING[instance.pk] = old_slug


@receiver(post_save, sender=Article, dispatch_uid="seo_create_slug_redirect")
def create_slug_redirect(sender, instance, created, **kwargs):
    old_slug = _PENDING.pop(instance.pk, None)
    if not old_slug:
        return

    source = f"/articles/{old_slug}"
    target = f"/articles/{instance.slug}"
    if source == target:
        return

    # Repoint any redirect that used to end at the old URL, so a slug changed
    # twice does not leave a chain (A -> B -> C) for crawlers to walk.
    Redirect.objects.filter(site=instance.site, target_path=source).update(
        target_path=target
    )

    Redirect.objects.update_or_create(
        site=instance.site,
        source_path=source,
        defaults={
            "target_path": target,
            "status_code": 301,
            "is_active": True,
            "note": "Created automatically when the slug changed.",
        },
    )

    # A redirect must never point at itself: if the new slug previously had a
    # redirect away from it, that rule is now wrong.
    Redirect.objects.filter(site=instance.site, source_path=target).delete()
