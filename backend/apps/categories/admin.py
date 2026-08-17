from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Registered for the Django shell's benefit, not for editors.

    The studio at `/studio/taxonomy` is the tool for this; the Django admin is
    no longer served (see config/urls.py). Kept so `manage.py` introspection
    and any future internal tooling still sees a sensible representation.
    """

    list_display = ("name", "slug", "depth", "url_path", "is_active", "order")
    list_filter = ("is_active", "depth")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("path", "url_path", "depth")
