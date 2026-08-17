"""Regression tests for media upload validation.

Two bugs are guarded here:
  1. MediaUploadView created MediaFile rows directly, so the 50MB cap and the
     MIME allowlist never ran on the primary upload path at all.
  2. Validation was filename-based, so renaming ``evil.svg`` to ``evil.png``
     bypassed it.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers as drf_serializers

from apps.media_library.validation import (
    MAX_FILE_SIZE,
    file_type_for,
    sniff_mime,
    validate_upload,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 28
GIF = b"GIF89a" + b"\x00" * 26
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 20
MP3 = b"ID3\x03\x00" + b"\x00" * 27
MP4 = b"\x00\x00\x00\x20" + b"ftyp" + b"isom" + b"\x00" * 20
M4A = b"\x00\x00\x00\x20" + b"ftyp" + b"M4A " + b"\x00" * 20
MOV = b"\x00\x00\x00\x20" + b"ftyp" + b"qt  " + b"\x00" * 20
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 28
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
HTML = b"<!doctype html><html><body>hi</body></html>"


def upload(name, payload):
    return SimpleUploadedFile(name, payload)


class TestSniffing:
    @pytest.mark.parametrize(
        "payload,expected",
        [
            (PNG, "image/png"),
            (JPEG, "image/jpeg"),
            (GIF, "image/gif"),
            (WEBP, "image/webp"),
            (WAV, "audio/wav"),
            (MP3, "audio/mpeg"),
            (MP4, "video/mp4"),
            (M4A, "audio/mp4"),
            (MOV, "video/quicktime"),
            (WEBM, "video/webm"),
        ],
    )
    def test_known_formats(self, payload, expected):
        assert sniff_mime(payload) == expected

    @pytest.mark.parametrize("payload", [SVG, HTML, b"", b"random-bytes-here"])
    def test_unknown_formats(self, payload):
        assert sniff_mime(payload) not in {
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        }

    def test_file_type_mapping(self):
        assert file_type_for("image/png") == "image"
        assert file_type_for("audio/mpeg") == "audio"
        assert file_type_for("video/mp4") == "video"


class TestValidateUpload:
    def test_accepts_a_real_png(self):
        assert validate_upload(upload("a.png", PNG)) == ("image", "image/png")

    def test_accepts_a_real_mp3(self):
        assert validate_upload(upload("a.mp3", MP3)) == ("audio", "audio/mpeg")

    def test_rejects_svg_even_when_named_svg(self):
        # SVG is XML that can carry <script>; serving it from our origin is
        # stored XSS, so it is excluded from the allowlist entirely.
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(upload("a.svg", SVG))

    def test_rejects_svg_renamed_to_png(self):
        # The core bypass: the old filename-based check accepted this.
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(upload("evil.png", SVG))

    def test_rejects_html_renamed_to_jpg(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(upload("evil.jpg", HTML))

    def test_rejects_content_extension_mismatch(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(upload("a.mp3", PNG))

    def test_accepts_mp4_extension_for_m4a_content(self):
        # .mp4 legitimately holds either audio or video.
        assert validate_upload(upload("a.mp4", M4A)) == ("audio", "audio/mp4")

    def test_rejects_empty_file(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(upload("a.png", b""))

    def test_rejects_oversized_file(self):
        big = upload("a.png", PNG)
        big.size = MAX_FILE_SIZE + 1
        with pytest.raises(drf_serializers.ValidationError):
            validate_upload(big)

    def test_stream_is_rewound_for_saving(self):
        # Sniffing must not consume the stream, or the saved file loses bytes.
        f = upload("a.png", PNG)
        validate_upload(f)
        assert f.read() == PNG


@pytest.mark.django_db
class TestUploadEndpoint:
    url = "/api/v1/studio/media/upload/"

    @pytest.fixture(autouse=True)
    def _member(self, author, default_site, membership_factory):
        # Upload moved onto the studio surface, which requires membership of
        # the site being uploaded to -- a global `author` role is no longer
        # sufficient on its own. Granted here so these tests stay about file
        # validation rather than re-testing permissions.
        membership_factory(author, default_site, role="author")

    def test_author_can_upload_valid_image(self, auth_client, author):
        client = auth_client(author)
        response = client.post(
            self.url, {"image": upload("a.png", PNG)}, format="multipart"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] == 1
        # The Editor.js contract: exact keys, or the editor tools break.
        assert set(body["file"]) == {"url", "id", "name", "size", "type"}
        assert body["file"]["type"] == "image"

    def test_upload_rejects_disguised_svg(self, auth_client, author):
        client = auth_client(author)
        response = client.post(
            self.url, {"image": upload("evil.png", SVG)}, format="multipart"
        )
        assert response.status_code == 400
        assert response.json()["success"] == 0

    def test_upload_rejects_oversized_file(self, auth_client, author, monkeypatch):
        # Shrink the cap rather than posting 50MB through the test client.
        # Setting ``.size`` on the SimpleUploadedFile would not survive, since
        # the multipart body is re-parsed into a fresh UploadedFile.
        monkeypatch.setattr("apps.media_library.validation.MAX_FILE_SIZE", 16)
        client = auth_client(author)
        response = client.post(
            self.url, {"image": upload("big.png", PNG + b"\x00" * 64)}, format="multipart"
        )
        assert response.status_code == 400
        assert response.json()["success"] == 0

    def test_upload_accepts_file_field_name_too(self, auth_client, author):
        # Editor.js sends "image" for the image tool and "file" for others.
        client = auth_client(author)
        response = client.post(
            self.url, {"file": upload("a.mp3", MP3)}, format="multipart"
        )
        assert response.status_code == 200
        assert response.json()["file"]["type"] == "audio"

    def test_anonymous_cannot_upload(self, api_client):
        response = api_client.post(
            self.url, {"image": upload("a.png", PNG)}, format="multipart"
        )
        assert response.status_code in (401, 403)

    def test_reader_cannot_upload(self, auth_client, reader):
        client = auth_client(reader)
        response = client.post(
            self.url, {"image": upload("a.png", PNG)}, format="multipart"
        )
        assert response.status_code in (401, 403)

    def test_missing_file_returns_400(self, auth_client, author):
        client = auth_client(author)
        response = client.post(self.url, {}, format="multipart")
        assert response.status_code == 400
        assert response.json()["success"] == 0
