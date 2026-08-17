"""Media upload.

Reading and editing media is the studio's job (``apps.studio.views``); this
module holds only the multipart upload endpoint, because its response shape is
dictated by Editor.js rather than by our own API conventions and does not
belong next to serializer-shaped views.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasSiteRole

from .models import MediaFile
from .serializers import MediaUploadSerializer
from .validation import validate_upload


@extend_schema(tags=["Studio"])
class MediaUploadView(APIView):
    """POST /api/v1/studio/media/upload/

    The response shape (``{success, file: {url, id, name, size, type}}``) is
    **required verbatim** by the Editor.js image and attachment tools -- they
    read those exact keys and silently drop the block if any is missing. It is
    not our envelope to tidy.

    Accepts either ``image`` or ``file`` as the field name, because the two
    Editor.js tools disagree about which they send.
    """

    permission_classes = (IsAuthenticated, HasSiteRole)
    required_site_role = "author"
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    @extend_schema(request=MediaUploadSerializer, responses={200: dict})
    def post(self, request):
        uploaded_file = request.FILES.get("image") or request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"success": 0, "message": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # This view previously called MediaFile.objects.create() directly, so
        # the size cap and MIME allowlist on MediaFileSerializer.validate_file
        # never ran on the primary upload path. Validate by content here.
        try:
            file_type, mime_type = validate_upload(uploaded_file)
        except ValidationError as exc:
            return Response(
                {"success": 0, "message": " ".join(exc.detail)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        media_file = MediaFile.objects.create(
            site=request.site,
            file=uploaded_file,
            file_type=file_type,
            mime_type=mime_type or "",
            uploaded_by=request.user,
        )

        return Response(
            {
                "success": 1,
                "file": {
                    "url": request.build_absolute_uri(media_file.file.url),
                    "id": media_file.id,
                    "name": media_file.title,
                    "size": media_file.file_size,
                    "type": media_file.file_type,
                },
            }
        )
