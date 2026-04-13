import nh3
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.categories.serializers import CategoryListSerializer, SubCategorySerializer

from .models import Article

User = get_user_model()

ALLOWED_BLOCK_TYPES = {
    "paragraph", "header", "image", "video", "audio", "youtube", "embed",
    "quote", "list", "delimiter", "table", "code", "warning",
    "interactive_text", "interactive_image",
    "interactive_audio", "interactive_video", "interactive_youtube",
    "raw",
}


def sanitize_block_text(text):
    """Sanitize HTML in block text to prevent XSS."""
    if not isinstance(text, str):
        return text
    return nh3.clean(
        text,
        tags={"b", "i", "u", "a", "br", "em", "strong", "mark", "code", "span"},
        attributes={"a": {"href", "target"}, "span": {"class", "data-modal-id", "data-annotation-id", "data-annotation-icon", "data-annotation"}},
    )


def sanitize_block_value(value):
    if isinstance(value, str):
        return sanitize_block_text(value)
    if isinstance(value, list):
        return [sanitize_block_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_block_value(val) for key, val in value.items()}
    return value


def validate_blocks(content):
    """Validate Editor.js block content."""
    if not isinstance(content, dict):
        raise serializers.ValidationError("Content must be a JSON object.")

    blocks = content.get("blocks", [])
    if not isinstance(blocks, list):
        raise serializers.ValidationError("Content 'blocks' must be a list.")

    sanitized_blocks = []
    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if not isinstance(block_type, str) or not block_type:
            continue

        data = block.get("data", {})
        if not isinstance(data, dict):
            data = {}

        sanitized_block = {
            "type": block_type,
            "data": sanitize_block_value(data),
        }
        if "id" in block:
            sanitized_block["id"] = block.get("id")
        sanitized_blocks.append(sanitized_block)

    if not sanitized_blocks:
        content["blocks"] = []
        return content

    unknown_block_types = {
        block.get("type")
        for block in sanitized_blocks
        if block.get("type") not in ALLOWED_BLOCK_TYPES
    }
    if unknown_block_types:
        raise serializers.ValidationError(
            f"Unsupported block type(s): {', '.join(sorted(unknown_block_types))}."
        )

    content["blocks"] = sanitized_blocks
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
    featured_image = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Article
        fields = (
            "id", "title", "category", "subcategory", "content",
            "excerpt", "featured_image", "status", "is_featured",
        )

    def validate_content(self, value):
        return validate_blocks(value)

    def validate_featured_image(self, value):
        return value or ""

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
