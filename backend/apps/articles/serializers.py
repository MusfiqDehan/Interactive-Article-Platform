import nh3
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.categories.serializers import CategoryListSerializer, SubCategorySerializer

from .models import Article

User = get_user_model()

ALLOWED_BLOCK_TYPES = {
    "paragraph", "header", "image", "video", "audio", "youtube", "embed",
    "quote", "list", "delimiter", "table", "code", "warning",
    "interactive_text", "interactive_image", "raw",
}


def sanitize_block_text(text):
    """Sanitize HTML in block text to prevent XSS."""
    if not isinstance(text, str):
        return text
    return nh3.clean(
        text,
        tags={"b", "i", "u", "a", "br", "em", "strong", "mark", "code", "span"},
        attributes={"a": {"href", "target", "rel"}, "span": {"class", "data-modal-id"}},
    )


def validate_blocks(content):
    """Validate Editor.js block content."""
    if not isinstance(content, dict):
        raise serializers.ValidationError("Content must be a JSON object.")

    blocks = content.get("blocks", [])
    if not isinstance(blocks, list):
        raise serializers.ValidationError("Content 'blocks' must be a list.")

    for block in blocks:
        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            raise serializers.ValidationError(f"Block type '{block_type}' is not allowed.")

        data = block.get("data", {})
        if "text" in data:
            data["text"] = sanitize_block_text(data["text"])

        # Sanitize caption for media blocks
        if "caption" in data:
            data["caption"] = sanitize_block_text(data["caption"])

        # Sanitize list items
        if block_type == "list" and "items" in data:
            data["items"] = [
                sanitize_block_text(item) if isinstance(item, str) else item
                for item in data["items"]
            ]

    return content


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "avatar")


class ArticleListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategoryListSerializer(read_only=True)

    class Meta:
        model = Article
        fields = (
            "id", "title", "slug", "author", "category", "excerpt",
            "featured_image", "status", "is_featured", "reading_time",
            "views_count", "published_at", "created_at",
        )


class ArticleDetailSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategoryListSerializer(read_only=True)
    subcategory = SubCategorySerializer(read_only=True)

    class Meta:
        model = Article
        fields = (
            "id", "title", "slug", "author", "category", "subcategory",
            "content", "excerpt", "featured_image", "status", "is_featured",
            "reading_time", "views_count", "published_at", "created_at", "updated_at",
        )


class ArticleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = (
            "id", "title", "category", "subcategory", "content",
            "excerpt", "featured_image", "status", "is_featured",
        )

    def validate_content(self, value):
        return validate_blocks(value)

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
