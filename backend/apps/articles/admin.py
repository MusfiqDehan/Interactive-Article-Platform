from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "status", "is_featured", "views_count", "published_at")
    list_filter = ("status", "is_featured", "category", "created_at")
    search_fields = ("title", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("views_count", "reading_time")
    date_hierarchy = "created_at"
