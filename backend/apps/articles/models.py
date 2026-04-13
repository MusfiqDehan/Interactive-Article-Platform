import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Article(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    )

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True, allow_unicode=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    subcategory = models.ForeignKey(
        "categories.SubCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    content = models.JSONField(
        default=dict,
        help_text="Editor.js block content stored as JSON",
    )
    excerpt = models.TextField(blank=True, default="", max_length=500)
    featured_image = models.URLField(blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    is_featured = models.BooleanField(default=False)
    reading_time = models.PositiveIntegerField(default=0, help_text="Estimated reading time in minutes")
    views_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "articles"
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)
            if not base_slug:
                base_slug = uuid.uuid4().hex[:8]
            slug = base_slug
            counter = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()

        # Estimate reading time from content blocks
        if self.content and isinstance(self.content, dict):
            word_count = 0
            for block in self.content.get("blocks", []):
                data = block.get("data", {})
                text = data.get("text", "")
                if isinstance(text, str):
                    word_count += len(text.split())
                items = data.get("items", [])
                for item in items:
                    if isinstance(item, str):
                        word_count += len(item.split())
            self.reading_time = max(1, word_count // 200)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
