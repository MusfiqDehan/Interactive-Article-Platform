"""Unicode-safe slug generation.

``django.utils.text.slugify(allow_unicode=True)`` strips every Unicode
combining mark, because its ``[^\\w\\s-]`` filter only keeps characters where
``str.isalnum()`` is true -- and marks are category Mn/Mc, not L/N.

For Indic scripts the marks *are* the vowels. Bengali "যান্ত্রিক" comes out as
"যনতরক", and three genuinely different words -- অনুবাদ, অনবাদ, অনুবদ -- all
collapse to the single slug "অনবদ". That is both an unreadable URL and a real
collision: the uniqueness loop then appends -1/-2 to unrelated articles.

This module keeps marks, so slugs stay faithful to the source text.
"""

from __future__ import annotations

import re
import unicodedata

# Percent-encoding inflates non-ASCII roughly 3x (one 3-byte UTF-8 codepoint
# becomes 9 characters), so an 80-character Bengali slug is already ~720 bytes
# in a URL. Cap generation well below common proxy/CDN URL limits.
MAX_SLUG_LENGTH = 80

_SEPARATOR_RE = re.compile(r"[-\s]+")

# Marks that carry vowel/consonant information in Indic and other scripts.
_MARK_CATEGORIES = frozenset({"Mn", "Mc"})


def _is_slug_char(char: str) -> bool:
    if char.isalnum() or char in "-_":
        return True
    return unicodedata.category(char) in _MARK_CATEGORIES


def unicode_slugify(value: str, *, max_length: int = MAX_SLUG_LENGTH) -> str:
    """Slugify ``value``, preserving Unicode combining marks.

    Returns ``""`` when nothing slug-worthy survives; callers are expected to
    fall back to a generated identifier.
    """
    if not value:
        return ""

    # NFC composes marks onto their base character where a composed form exists,
    # which keeps equivalent spellings from producing different slugs.
    text = unicodedata.normalize("NFC", str(value)).lower()
    kept = [char if _is_slug_char(char) else " " if char.isspace() else "" for char in text]
    slug = _SEPARATOR_RE.sub("-", "".join(kept)).strip("-_")

    if max_length and len(slug) > max_length:
        slug = slug[:max_length].rstrip("-_")
        # Avoid cutting a word in half when a hyphen is close to the boundary.
        if "-" in slug and len(slug) > max_length * 0.6:
            head, _, tail = slug.rpartition("-")
            if head and len(head) >= max_length * 0.5:
                slug = head
    return slug


def unique_slug(value: str, queryset, *, field: str = "slug", fallback: str = "") -> str:
    """Return a slug for ``value`` that is unique within ``queryset``.

    ``queryset`` should already exclude the instance being saved.
    """
    base = unicode_slugify(value) or fallback
    if not base:
        return ""

    slug = base
    counter = 1
    # Leave room for the "-N" suffix so long slugs cannot overflow the column.
    trim_to = MAX_SLUG_LENGTH - 6
    while queryset.filter(**{field: slug}).exists():
        if len(base) > trim_to:
            base = base[:trim_to].rstrip("-_")
        slug = f"{base}-{counter}"
        counter += 1
    return slug
