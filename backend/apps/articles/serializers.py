"""Editor.js block sanitisation and validation.

This module is shared by every surface that accepts blocks. It holds no
serializers of its own any more -- the four that lived here belonged to the
removed legacy API, and the studio defines its own in `apps.studio`.
"""

import uuid
from urllib.parse import urlparse

import nh3
from rest_framework import serializers

from common.blocks import ANNOTATION_CONTAINERS
from common.blocks import URL_KEYS as BLOCK_URL_KEYS

ALLOWED_BLOCK_TYPES = {
    "paragraph", "header", "image", "video", "audio", "youtube", "embed",
    "quote", "list", "delimiter", "table", "code", "warning",
    "interactive_text", "interactive_image",
    "interactive_audio", "interactive_video", "interactive_youtube",
    "raw",
}


# Inline-only markup, used for a block's own ``text`` -- block-level tags here
# would break the paragraph layout.
INLINE_TAGS = {"b", "i", "u", "a", "br", "em", "strong", "mark", "code", "span"}

# Richer markup, permitted only inside annotation/hotspot/chapter bodies and
# captions. Those render into their own container (a modal, or the server-side
# <details> appendix), so block-level structure is both safe and expected.
RICH_TAGS = INLINE_TAGS | {
    "p", "h2", "h3", "h4", "ul", "ol", "li", "blockquote",
    "figure", "figcaption", "img", "table", "thead", "tbody",
    "tr", "td", "th", "pre", "hr", "sub", "sup", "small",
}

SHARED_ATTRIBUTES = {
    # NB: "rel" must not appear here. Ammonia manages rel itself (link_rel) and
    # panics at runtime if the caller also allowlists it.
    "a": {"href", "target", "title"},
    "span": {
        "class",
        "data-modal-id",
        "data-annotation-id",
        "data-annotation-icon",
        "data-annotation",
    },
}
RICH_ATTRIBUTES = {
    **SHARED_ATTRIBUTES,
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}

# Keys whose values may carry rich markup.
RICH_TEXT_KEYS = frozenset({"modal_content", "caption", "image_caption", "message"})

# Keys whose values are addresses, not markup. Sourced from common.blocks so the
# extractor and the sanitizer can never disagree about what counts as a URL.
URL_KEYS = BLOCK_URL_KEYS

ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto"})


def sanitize_block_text(text, *, rich=False):
    """Sanitize an HTML fragment from block content.

    ``rich=True`` permits block-level structure and is used for annotation
    bodies and captions; the default inline-only set is used for a block's own
    ``text``.
    """
    if not isinstance(text, str):
        return text
    return nh3.clean(
        text,
        tags=RICH_TAGS if rich else INLINE_TAGS,
        attributes=RICH_ATTRIBUTES if rich else SHARED_ATTRIBUTES,
    )


def sanitize_url(value):
    """Validate a URL without running it through the HTML sanitizer.

    Passing a URL through ``nh3.clean`` HTML-escapes its ampersands, so
    ``?a=1&t=5`` silently becomes ``?a=1&amp;t=5`` on every save -- permanently
    corrupting multi-parameter YouTube links and presigned storage URLs. URLs
    are therefore scheme-checked instead of markup-cleaned.
    """
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate:
        return ""
    # Protocol-relative URLs inherit the page scheme and bypass the check below,
    # so require either a site-relative path or an explicit allowed scheme.
    if candidate.startswith("//"):
        return ""
    if candidate.startswith("/"):
        return candidate
    scheme = urlparse(candidate).scheme.lower()
    if scheme in ALLOWED_URL_SCHEMES:
        return candidate
    # Drops javascript:, data:, vbscript: and anything else unrecognised.
    return ""


def sanitize_block_value(value, key=None, *, rich=False):
    """Recursively sanitize a block ``data`` payload.

    The treatment depends on the *key* a string sits under, not on its type:
    URLs are validated, annotation bodies get the rich allowlist, everything
    else gets the inline allowlist.
    """
    if isinstance(value, str):
        if key in URL_KEYS:
            return sanitize_url(value)
        return sanitize_block_text(value, rich=rich or key in RICH_TEXT_KEYS)
    if isinstance(value, list):
        # Lists inherit their parent's key so ``items``/``content`` cells and
        # annotation arrays are each treated consistently.
        return [sanitize_block_value(item, key, rich=rich) for item in value]
    if isinstance(value, dict):
        # Entering an annotation-like container switches on rich markup for the
        # whole subtree, so nested modal bodies keep their structure.
        nested_rich = rich or key in ANNOTATION_CONTAINERS
        return {
            child_key: sanitize_block_value(child, child_key, rich=nested_rich)
            for child_key, child in value.items()
        }
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

        # Every block needs a stable id: review comments anchor to it and
        # revision diffs are computed against it. Editor.js normally supplies
        # one, but backfill rather than trust -- an id that appears later would
        # orphan any comment already attached to the block.
        block_id = block.get("id")
        if not isinstance(block_id, str) or not block_id:
            block_id = uuid.uuid4().hex[:10]

        sanitized_blocks.append(
            {
                "id": block_id,
                "type": block_type,
                "data": sanitize_block_value(data),
            }
        )

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
