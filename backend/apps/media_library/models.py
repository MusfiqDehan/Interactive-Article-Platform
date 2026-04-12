import os

from django.conf import settings
from django.db import models


class MediaFile(models.Model):
    FILE_TYPE_CHOICES = (
        ("image", "Image"),
        ("audio", "Audio"),
        ("video", "Video"),
        ("document", "Document"),
    )

    file = models.FileField(upload_to="uploads/%Y/%m/")
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True, default="")
    alt_text = models.CharField(max_length=255, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True, default="")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="media_files",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "media_library"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.title:
            self.title = os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or str(self.file)
