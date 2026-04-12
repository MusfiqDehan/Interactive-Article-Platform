import mimetypes

from rest_framework import serializers

from .models import MediaFile

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


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
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(f"File size must be under {MAX_FILE_SIZE // (1024*1024)}MB.")

        mime_type, _ = mimetypes.guess_type(value.name)
        allowed = ALLOWED_IMAGE_TYPES | ALLOWED_AUDIO_TYPES | ALLOWED_VIDEO_TYPES
        if mime_type and mime_type not in allowed:
            raise serializers.ValidationError(f"File type '{mime_type}' is not allowed.")

        return value


class MediaUploadSerializer(serializers.Serializer):
    """Serializer for Editor.js compatible upload response."""
    image = serializers.FileField(required=False)
    file = serializers.FileField(required=False)

    def validate(self, attrs):
        if not attrs.get("image") and not attrs.get("file"):
            raise serializers.ValidationError("Either 'image' or 'file' field is required.")
        return attrs
