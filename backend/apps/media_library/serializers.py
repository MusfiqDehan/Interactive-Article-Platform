from rest_framework import serializers

from .models import MediaFile
from .validation import (  # noqa: F401  (re-exported for backwards compatibility)
    ALLOWED_AUDIO_TYPES,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILE_SIZE,
    validate_upload,
)


class MediaFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MediaFile
        fields = ("id", "file", "url", "file_type", "title", "alt_text", "file_size", "mime_type", "uploaded_by", "created_at")
        read_only_fields = ("id", "file_size", "mime_type", "uploaded_by", "created_at")

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return ""

    def validate_file(self, value):
        # Shares one implementation with MediaUploadView so the two upload paths
        # can never drift apart on what they accept.
        validate_upload(value)
        return value


class MediaUploadSerializer(serializers.Serializer):
    """Serializer for Editor.js compatible upload response."""
    image = serializers.FileField(required=False)
    file = serializers.FileField(required=False)

    def validate(self, attrs):
        if not attrs.get("image") and not attrs.get("file"):
            raise serializers.ValidationError("Either 'image' or 'file' field is required.")
        return attrs
