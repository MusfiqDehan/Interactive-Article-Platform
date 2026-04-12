from django.contrib import admin

from .models import MediaFile


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ("title", "file_type", "file_size", "uploaded_by", "created_at")
    list_filter = ("file_type", "created_at")
    search_fields = ("title", "alt_text")
    readonly_fields = ("file_size", "mime_type")
