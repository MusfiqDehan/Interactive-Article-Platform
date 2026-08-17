"""Upload validation based on file *content*, not filename.

``mimetypes.guess_type()`` reads the extension, so renaming ``evil.svg`` to
``evil.png`` defeats it entirely. Everything here sniffs magic bytes instead and
then cross-checks the extension, rejecting mismatches.

Deliberately stdlib-only: ``python-magic`` would pull in a libmagic system
package for what amounts to a few dozen byte signatures.
"""

from __future__ import annotations

import mimetypes

from rest_framework import serializers

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# SVG is intentionally absent. It is XML that can carry <script> and event
# handlers, so serving user-supplied SVG from our own origin is a stored-XSS
# vector. Accepting it would require a separate sanitizing pass.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
ALLOWED_MIME_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_AUDIO_TYPES | ALLOWED_VIDEO_TYPES

# (offset, signature, mime). Order matters: container formats that need a brand
# check are handled separately below.
_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"ID3", "audio/mpeg"),
    (0, b"\xff\xfb", "audio/mpeg"),
    (0, b"\xff\xf3", "audio/mpeg"),
    (0, b"\xff\xf2", "audio/mpeg"),
    (0, b"OggS", "application/ogg"),  # refined by codec below
    (0, b"\x1a\x45\xdf\xa3", "video/webm"),
)

# ISO base-media brands (bytes 8..12, after the "ftyp" box marker at offset 4).
_FTYP_BRANDS: tuple[tuple[bytes, str], ...] = (
    (b"M4A ", "audio/mp4"),
    (b"M4B ", "audio/mp4"),
    (b"qt  ", "video/quicktime"),
)

_HEADER_BYTES = 32


def sniff_mime(header: bytes) -> str | None:
    """Identify a MIME type from a file's leading bytes."""
    if not header:
        return None

    # RIFF containers: the sub-type at offset 8 decides image vs audio.
    if header[:4] == b"RIFF" and len(header) >= 12:
        sub = header[8:12]
        if sub == b"WEBP":
            return "image/webp"
        if sub == b"WAVE":
            return "audio/wav"
        return None

    # ISO base media (mp4/m4a/mov): "ftyp" marker at offset 4.
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        for candidate, mime in _FTYP_BRANDS:
            if brand == candidate:
                return mime
        return "video/mp4"

    for offset, signature, mime in _SIGNATURES:
        if header[offset : offset + len(signature)] == signature:
            if mime == "application/ogg":
                # Ogg carries either Vorbis/Opus audio or Theora video.
                return "video/ogg" if b"theora" in header else "audio/ogg"
            return mime

    return None


def file_type_for(mime_type: str) -> str:
    if mime_type in ALLOWED_IMAGE_TYPES:
        return "image"
    if mime_type in ALLOWED_AUDIO_TYPES:
        return "audio"
    if mime_type in ALLOWED_VIDEO_TYPES:
        return "video"
    return "document"


def _read_header(uploaded_file) -> bytes:
    """Read the leading bytes without consuming the stream for later saving."""
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(_HEADER_BYTES)
    finally:
        uploaded_file.seek(0)
    return header or b""


def validate_upload(uploaded_file) -> tuple[str, str]:
    """Validate an uploaded file and return ``(file_type, mime_type)``.

    Raises ``serializers.ValidationError`` on size, type, or extension/content
    mismatch.
    """
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_FILE_SIZE:
        raise serializers.ValidationError(
            f"File size must be under {MAX_FILE_SIZE // (1024 * 1024)}MB."
        )
    if not size:
        raise serializers.ValidationError("Uploaded file is empty.")

    sniffed = sniff_mime(_read_header(uploaded_file))
    if sniffed is None:
        raise serializers.ValidationError(
            "Unrecognised file type. Allowed: JPEG, PNG, GIF, WebP, MP3, WAV, "
            "OGG, MP4, WebM, QuickTime."
        )
    if sniffed not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(f"File type '{sniffed}' is not allowed.")

    # Cross-check the extension. A mismatch means the file was renamed to slip
    # past extension-based checks elsewhere in the stack (or a CDN sniffing it).
    declared, _ = mimetypes.guess_type(getattr(uploaded_file, "name", "") or "")
    if declared and declared not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(
            f"File extension implies '{declared}', which is not allowed."
        )
    if declared and not _compatible(declared, sniffed):
        raise serializers.ValidationError(
            f"File content ({sniffed}) does not match its extension ({declared})."
        )

    return file_type_for(sniffed), sniffed


# Extensions that legitimately map to several sniffed types.
_EQUIVALENT: tuple[frozenset[str], ...] = (
    frozenset({"video/mp4", "audio/mp4"}),
    frozenset({"audio/ogg", "video/ogg"}),
    frozenset({"video/webm", "audio/webm"}),
)


def _compatible(declared: str, sniffed: str) -> bool:
    if declared == sniffed:
        return True
    return any(
        declared in group and sniffed in group for group in _EQUIVALENT
    )
