"""Editor.js block traversal: text extraction and annotation harvesting.

This is the single place that knows how to read text out of a block payload.
Five subsystems depend on it -- reading time, the search index, SEO analysis,
the server-rendered annotation appendix, and social caption fallbacks -- so it
must stay exhaustive and side-effect free.

Two rules govern everything here:

1. **Never treat a URL as prose.** ``image_url``/``youtube_source``/``file.url``
   and friends are addresses, not text. Feeding them to the word counter
   inflates reading time and pollutes the search index.
2. **Never concatenate across a tag boundary.** ``<h2>Title</h2><p>Body</p>``
   must extract as ``"Title Body"``, not ``"TitleBody"``. Word counts and
   keyword density are both wrong if adjacent blocks fuse into one token.
"""

from __future__ import annotations

import html as html_module
import json
import re
from collections.abc import Iterator
from typing import Any

# Keys whose values are prose and should be walked for text.
TEXT_KEYS = ("text", "caption", "code", "message", "title", "label")

# Keys whose values are addresses. Excluded from text extraction entirely, and
# excluded from HTML sanitization by the serializer (see apps.articles.serializers).
URL_KEYS = frozenset(
    {
        "url",
        "src",
        "source",
        "image_url",
        "audio_url",
        "video_url",
        "youtube_source",
        "youtube_url",
        "embed",
    }
)

# Lists of annotation-like objects hanging off a block's ``data``.
ANNOTATION_CONTAINERS = ("annotations", "hotspots", "chapters")

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


def html_to_text(value: str) -> str:
    """Flatten an HTML fragment to plain text.

    Tags collapse to a single space so that word boundaries survive, then HTML
    entities are decoded and whitespace normalised. The output is only ever used
    for counting, indexing and analysis -- never re-rendered as HTML.
    """
    if not isinstance(value, str) or not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = html_module.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _iter_container_text(container: str, entry: dict) -> Iterator[tuple[str, str]]:
    """Yield prose out of one annotation/hotspot/chapter object."""
    kind = entry.get("type") or container.rstrip("s")
    for key in ("modal_title", "modal_content", "label", "image_caption"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            yield f"annotation:{kind}", value


def iter_block_text(
    content: Any, *, include_annotations: bool = True
) -> Iterator[tuple[str, str]]:
    """Yield ``(source, raw_html)`` for every piece of prose in ``content``.

    ``source`` is a coarse label such as ``block:paragraph`` or
    ``annotation:image``, letting callers weight or filter by origin.
    """
    if not isinstance(content, dict):
        return
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type") or "unknown"
        data = block.get("data")
        if not isinstance(data, dict):
            continue

        for key in TEXT_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                yield f"block:{btype}", value

        # Lists: items are either plain strings or ``{"content": ...}`` objects
        # (Editor.js changed the shape between major versions; both appear).
        for item in data.get("items") or []:
            if isinstance(item, str) and item.strip():
                yield f"block:{btype}", item
            elif isinstance(item, dict):
                inner = item.get("content")
                if isinstance(inner, str) and inner.strip():
                    yield f"block:{btype}", inner

        # Tables: ``data["content"]`` is a list of rows, each a list of cells.
        table = data.get("content")
        if isinstance(table, list):
            for row in table:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    if isinstance(cell, str) and cell.strip():
                        yield f"block:{btype}", cell

        if not include_annotations:
            continue

        for container in ANNOTATION_CONTAINERS:
            for entry in data.get(container) or []:
                if isinstance(entry, dict):
                    yield from _iter_container_text(container, entry)

        # Inline annotations live inside the paragraph HTML rather than in a
        # sibling array, so they need parsing out of the markup.
        text = data.get("text")
        if isinstance(text, str) and "data-annotation" in text:
            for record in _parse_inline_annotations(text):
                for key in ("modal_title", "modal_content", "image_caption"):
                    value = record.get(key)
                    if isinstance(value, str) and value.strip():
                        yield f"annotation:{record.get('type', 'text')}", value


def blocks_to_plaintext(content: Any, *, include_annotations: bool = True) -> str:
    """Flatten an entire block document to newline-separated plain text."""
    parts = [
        cleaned
        for _, raw in iter_block_text(content, include_annotations=include_annotations)
        if (cleaned := html_to_text(raw))
    ]
    return "\n".join(parts)


def count_words(content: Any, *, include_annotations: bool = True) -> int:
    return len(
        blocks_to_plaintext(content, include_annotations=include_annotations).split()
    )


# --------------------------------------------------------------------------
# Inline annotation parsing
# --------------------------------------------------------------------------

_ANNOTATION_ATTR_RE = re.compile(
    r'data-annotation\s*=\s*"([^"]*)"|data-annotation\s*=\s*\'([^\']*)\'',
    re.IGNORECASE,
)


def _parse_inline_annotations(text: str) -> list[dict]:
    """Pull annotation payloads out of ``data-annotation`` attributes.

    The editor packs a JSON object into the attribute. It arrives HTML-escaped,
    and the sanitizer partially decodes it on the way through, so we unescape
    defensively and skip anything that will not parse rather than raising --
    a single malformed annotation must never break a whole article's save.
    """
    records: list[dict] = []
    for match in _ANNOTATION_ATTR_RE.finditer(text or ""):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        if not raw:
            continue
        for candidate in (raw, html_module.unescape(raw)):
            try:
                parsed = json.loads(candidate)
            except (ValueError, TypeError):
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            break
    return records


_SPAN_RE = re.compile(
    r'<span\b[^>]*\bdata-annotation-id\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)


def _media_for(record: dict) -> dict | None:
    for key, media_type in (
        ("image_url", "image"),
        ("audio_url", "audio"),
        ("video_url", "video"),
        ("youtube_source", "youtube"),
    ):
        url = record.get(key)
        if isinstance(url, str) and url.strip():
            return {
                "url": url.strip(),
                "type": media_type,
                "alt": record.get("image_caption") or record.get("modal_title") or "",
            }
    return None


def extract_annotations(content: Any) -> list[dict]:
    """Return every annotation in the document, in reading order.

    Consumed by the public serializer (``annotations_index``), the search
    document builder, and the SEO analyzer. Covers all three carriers: the
    sibling ``annotations`` array, inline ``data-annotation`` attributes, and
    the hotspot/chapter containers.
    """
    results: list[dict] = []
    if not isinstance(content, dict):
        return results
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return results

    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = block.get("id") or ""
        btype = block.get("type") or "unknown"
        data = block.get("data")
        if not isinstance(data, dict):
            continue

        text = data.get("text") if isinstance(data.get("text"), str) else ""
        # Map annotation id -> the highlighted phrase it wraps, so the appendix
        # can show readers which words the note belongs to.
        labels = {
            aid: html_to_text(inner) for aid, inner in _SPAN_RE.findall(text or "")
        }

        # 1. Sibling array (interactive_text) and inline attributes (paragraph).
        records = [a for a in (data.get("annotations") or []) if isinstance(a, dict)]
        records.extend(_parse_inline_annotations(text))

        seen: set[str] = set()
        for record in records:
            aid = str(record.get("id") or "")
            if aid and aid in seen:
                continue
            if aid:
                seen.add(aid)
            modal_content = record.get("modal_content") or ""
            results.append(
                {
                    "id": aid,
                    "block_id": block_id,
                    "block_type": btype,
                    "kind": record.get("type") or "text",
                    "label": labels.get(aid, ""),
                    "title": record.get("modal_title") or "",
                    "html": modal_content,
                    "plain": html_to_text(modal_content),
                    "media": _media_for(record),
                    "time": None,
                }
            )

        # 2. Image hotspots.
        for hotspot in data.get("hotspots") or []:
            if not isinstance(hotspot, dict):
                continue
            modal_content = hotspot.get("modal_content") or ""
            results.append(
                {
                    "id": str(hotspot.get("id") or ""),
                    "block_id": block_id,
                    "block_type": btype,
                    "kind": "hotspot",
                    "label": hotspot.get("modal_title") or "",
                    "title": hotspot.get("modal_title") or "",
                    "html": modal_content,
                    "plain": html_to_text(modal_content),
                    "media": None,
                    "time": None,
                }
            )

        # 3. Media chapters.
        for chapter in data.get("chapters") or []:
            if not isinstance(chapter, dict):
                continue
            modal_content = chapter.get("modal_content") or ""
            time_value = chapter.get("time")
            results.append(
                {
                    "id": str(chapter.get("id") or ""),
                    "block_id": block_id,
                    "block_type": btype,
                    "kind": "chapter",
                    "label": chapter.get("label") or "",
                    "title": chapter.get("modal_title") or "",
                    "html": modal_content,
                    "plain": html_to_text(modal_content),
                    "media": None,
                    "time": time_value if isinstance(time_value, (int, float)) else None,
                }
            )

    return results
