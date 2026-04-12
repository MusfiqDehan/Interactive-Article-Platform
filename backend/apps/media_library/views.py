import mimetypes

from drf_spectacular.utils import extend_schema
from rest_framework import generics, parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminOrAuthor, IsOwnerOrAdmin

from .models import MediaFile
from .serializers import MediaFileSerializer, MediaUploadSerializer


@extend_schema(tags=["Media"])
class MediaUploadView(APIView):
    """Upload endpoint compatible with Editor.js image/file tools."""
    permission_classes = (IsAdminOrAuthor,)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    @extend_schema(request=MediaUploadSerializer, responses={200: dict})
    def post(self, request):
        uploaded_file = request.FILES.get("image") or request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"success": 0, "message": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
        file_type = "image"
        if mime_type:
            if mime_type.startswith("audio"):
                file_type = "audio"
            elif mime_type.startswith("video"):
                file_type = "video"

        media_file = MediaFile.objects.create(
            file=uploaded_file,
            file_type=file_type,
            mime_type=mime_type or "",
            uploaded_by=request.user,
        )

        file_url = request.build_absolute_uri(media_file.file.url)

        # Editor.js compatible response
        return Response({
            "success": 1,
            "file": {
                "url": file_url,
                "id": media_file.id,
                "name": media_file.title,
                "size": media_file.file_size,
                "type": media_file.file_type,
            },
        })


@extend_schema(tags=["Media"])
class MediaListView(generics.ListAPIView):
    serializer_class = MediaFileSerializer
    permission_classes = (IsAdminOrAuthor,)
    filterset_fields = ("file_type",)
    search_fields = ("title", "alt_text")

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return MediaFile.objects.all()
        return MediaFile.objects.filter(uploaded_by=user)


@extend_schema(tags=["Media"])
class MediaDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = MediaFileSerializer
    permission_classes = (IsOwnerOrAdmin,)
    queryset = MediaFile.objects.all()
