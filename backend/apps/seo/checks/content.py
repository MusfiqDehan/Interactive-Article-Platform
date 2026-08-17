"""The concrete SEO checks.

Weights are a judgement call, but the ordering is deliberate: things that
change whether a page can rank at all (title, description, word count, alt
text) outweigh polish (outbound links).

Every check that inspects images counts images **inside annotations** too --
on this platform a large share of the visual content lives there, and ignoring
it would report a clean bill of health on an article that is half unlabelled.
"""

from __future__ import annotations

import re

from common.blocks import html_to_text

from .base import (
    STATUS_FAIL,
    STATUS_OK,
    STATUS_WARN,
    CheckContext,
    CheckResult,
    register,
    word_list,
)


def _contains_keyword(haystack: str, keyword: str) -> bool:
    if not keyword:
        return False
    return keyword.lower().strip() in (haystack or "").lower()


# -- title ----------------------------------------------------------------


@register
def title_length(ctx: CheckContext) -> CheckResult:
    length = len(ctx.seo.meta_title or "")
    if 30 <= length <= 60:
        status, detail = STATUS_OK, f"{length} characters."
    elif length == 0:
        status, detail = STATUS_FAIL, "No title set."
    elif length < 30:
        status, detail = STATUS_WARN, f"{length} characters -- short; aim for 30-60."
    else:
        status, detail = STATUS_WARN, f"{length} characters -- Google will truncate it."
    return CheckResult("title_length", "Title length", status, 10, detail)


@register
def title_has_keyword(ctx: CheckContext) -> CheckResult:
    if not ctx.seo.focus_keyword:
        return CheckResult(
            "title_keyword", "Focus keyword in title", STATUS_WARN, 8,
            "No focus keyword set.",
        )
    ok = _contains_keyword(ctx.seo.meta_title, ctx.seo.focus_keyword)
    return CheckResult(
        "title_keyword", "Focus keyword in title",
        STATUS_OK if ok else STATUS_FAIL, 8,
        "Present." if ok else f"'{ctx.seo.focus_keyword}' is missing from the title.",
    )


# -- description ----------------------------------------------------------


@register
def description_length(ctx: CheckContext) -> CheckResult:
    length = len(ctx.seo.meta_description or "")
    if 120 <= length <= 158:
        status, detail = STATUS_OK, f"{length} characters."
    elif length == 0:
        status, detail = STATUS_FAIL, "No meta description."
    elif length < 120:
        status, detail = STATUS_WARN, f"{length} characters -- short; aim for 120-158."
    else:
        status, detail = STATUS_WARN, f"{length} characters -- will be truncated."
    return CheckResult("description_length", "Meta description length", status, 10, detail)


@register
def description_has_keyword(ctx: CheckContext) -> CheckResult:
    if not ctx.seo.focus_keyword:
        return CheckResult(
            "description_keyword", "Keyword in meta description", STATUS_WARN, 5,
            "No focus keyword set.",
        )
    ok = _contains_keyword(ctx.seo.meta_description, ctx.seo.focus_keyword)
    return CheckResult(
        "description_keyword", "Keyword in meta description",
        STATUS_OK if ok else STATUS_WARN, 5,
        "Present." if ok else "Not found in the description.",
    )


# -- body -----------------------------------------------------------------


@register
def keyword_in_opening(ctx: CheckContext) -> CheckResult:
    if not ctx.seo.focus_keyword:
        return CheckResult(
            "keyword_opening", "Keyword in first 100 words", STATUS_WARN, 8,
            "No focus keyword set.",
        )
    opening = " ".join(word_list(ctx.plain_text)[:100])
    ok = _contains_keyword(opening, ctx.seo.focus_keyword)
    return CheckResult(
        "keyword_opening", "Keyword in first 100 words",
        STATUS_OK if ok else STATUS_WARN, 8,
        "Present." if ok else "Introduce the keyword earlier.",
    )


@register
def keyword_density(ctx: CheckContext) -> CheckResult:
    keyword = (ctx.seo.focus_keyword or "").lower().strip()
    words = word_list(ctx.plain_text)
    if not keyword or not words:
        return CheckResult(
            "keyword_density", "Keyword density", STATUS_WARN, 6, "Cannot compute."
        )
    occurrences = len(re.findall(re.escape(keyword), ctx.plain_text.lower()))
    density = occurrences / len(words) * 100
    if 0.5 <= density <= 2.5:
        status, detail = STATUS_OK, f"{density:.1f}%"
    elif density < 0.5:
        status, detail = STATUS_WARN, f"{density:.1f}% -- used {occurrences}x; too sparse."
    else:
        status, detail = STATUS_WARN, f"{density:.1f}% -- reads as keyword stuffing."
    return CheckResult("keyword_density", "Keyword density", status, 6, detail)


@register
def word_count(ctx: CheckContext) -> CheckResult:
    count = len(word_list(ctx.plain_text))
    if count >= 600:
        status, detail = STATUS_OK, f"{count} words."
    elif count >= 300:
        status, detail = STATUS_WARN, f"{count} words -- thin for a competitive query."
    else:
        status, detail = STATUS_FAIL, f"{count} words -- likely to be seen as thin content."
    return CheckResult("word_count", "Word count", status, 8, detail)


@register
def slug_has_keyword(ctx: CheckContext) -> CheckResult:
    if not ctx.seo.focus_keyword:
        return CheckResult(
            "slug_keyword", "Keyword in slug", STATUS_WARN, 4, "No focus keyword set."
        )
    slug = (getattr(ctx.article, "slug", "") or "").replace("-", " ")
    ok = _contains_keyword(slug, ctx.seo.focus_keyword)
    return CheckResult(
        "slug_keyword", "Keyword in slug",
        STATUS_OK if ok else STATUS_WARN, 4,
        "Present." if ok else "The slug does not contain the focus keyword.",
    )


# -- structure ------------------------------------------------------------


def _headings(article) -> list[tuple[int, str, str]]:
    """Return ``(level, text, block_id)`` for every header block."""
    out = []
    for block in (article.content or {}).get("blocks", []):
        if not isinstance(block, dict) or block.get("type") != "header":
            continue
        data = block.get("data") or {}
        level = data.get("level")
        if isinstance(level, int):
            out.append((level, html_to_text(data.get("text", "")), block.get("id", "")))
    return out


@register
def has_subheadings(ctx: CheckContext) -> CheckResult:
    headings = _headings(ctx.article)
    h2s = [h for h in headings if h[0] == 2]
    ok = bool(h2s)
    return CheckResult(
        "has_h2", "Has subheadings",
        STATUS_OK if ok else STATUS_WARN, 6,
        f"{len(h2s)} H2 heading(s)." if ok else "No H2 headings; long text is hard to scan.",
    )


@register
def heading_hierarchy(ctx: CheckContext) -> CheckResult:
    headings = _headings(ctx.article)
    problems, anchors = [], []

    # The page title is already the H1, so a second one in the body competes.
    h1s = [h for h in headings if h[0] == 1]
    if h1s:
        problems.append(f"{len(h1s)} H1 in the body (the title is already the H1)")
        anchors.extend(h[2] for h in h1s)

    previous = 1
    for level, _text, block_id in headings:
        if level > previous + 1:
            problems.append(f"jumps H{previous} -> H{level}")
            anchors.append(block_id)
        previous = level

    if not problems:
        return CheckResult(
            "heading_hierarchy", "Heading hierarchy", STATUS_OK, 4, "Well formed."
        )
    return CheckResult(
        "heading_hierarchy", "Heading hierarchy", STATUS_WARN, 4,
        "; ".join(problems), anchors=[a for a in anchors if a],
    )


# -- images ---------------------------------------------------------------


def _images(article, annotations) -> list[tuple[str, str, str]]:
    """``(url, alt, block_id)`` for every image, annotations included."""
    found = []
    for block in (article.content or {}).get("blocks", []):
        if not isinstance(block, dict):
            continue
        data = block.get("data") or {}
        block_id = block.get("id", "")
        btype = block.get("type")
        if btype in ("image", "interactive_image"):
            url = (data.get("file") or {}).get("url") or data.get("url") or ""
            if url:
                found.append((url, data.get("caption") or "", block_id))
    # Images inside annotation modals count too -- on this platform they carry
    # a lot of the visual content.
    for annotation in annotations:
        media = annotation.get("media") or {}
        if media.get("type") == "image" and media.get("url"):
            found.append((media["url"], media.get("alt") or "", annotation.get("block_id", "")))
    return found


@register
def images_have_alt_text(ctx: CheckContext) -> CheckResult:
    images = _images(ctx.article, ctx.annotations)
    if not images:
        return CheckResult(
            "image_alt", "Images have alt text", STATUS_OK, 10, "No images."
        )
    missing = [img for img in images if not img[1].strip()]
    if not missing:
        return CheckResult(
            "image_alt", "Images have alt text", STATUS_OK, 10,
            f"All {len(images)} image(s) described.",
        )
    return CheckResult(
        "image_alt", "Images have alt text", STATUS_FAIL, 10,
        f"{len(missing)} of {len(images)} image(s) have no alt text.",
        anchors=[img[2] for img in missing if img[2]],
    )


@register
def has_featured_image(ctx: CheckContext) -> CheckResult:
    ok = bool(ctx.seo.og_image)
    return CheckResult(
        "featured_image", "Social share image", STATUS_OK if ok else STATUS_FAIL, 6,
        "Set." if ok else "No featured or OG image -- shared links will render bare.",
    )


# -- links ----------------------------------------------------------------


def _links(article) -> list[str]:
    hrefs = []
    for block in (article.content or {}).get("blocks", []):
        if not isinstance(block, dict):
            continue
        for value in (block.get("data") or {}).values():
            if isinstance(value, str):
                hrefs.extend(re.findall(r'href=["\']([^"\']+)["\']', value))
    return hrefs


@register
def has_internal_links(ctx: CheckContext) -> CheckResult:
    base = ctx.site.base_url if ctx.site else ""
    internal = [h for h in _links(ctx.article) if h.startswith("/") or (base and h.startswith(base))]
    ok = bool(internal)
    return CheckResult(
        "internal_links", "Internal links", STATUS_OK if ok else STATUS_WARN, 6,
        f"{len(internal)} internal link(s)." if ok else "None; link to related articles.",
    )


@register
def has_outbound_links(ctx: CheckContext) -> CheckResult:
    base = ctx.site.base_url if ctx.site else ""
    outbound = [
        h
        for h in _links(ctx.article)
        if h.startswith(("http://", "https://")) and not (base and h.startswith(base))
    ]
    ok = bool(outbound)
    return CheckResult(
        "outbound_links", "Outbound links", STATUS_OK if ok else STATUS_WARN, 3,
        f"{len(outbound)} outbound link(s)." if ok else "None; citing sources builds trust.",
    )


# -- technical ------------------------------------------------------------


@register
def has_canonical(ctx: CheckContext) -> CheckResult:
    ok = bool(ctx.seo.canonical_url)
    return CheckResult(
        "canonical", "Canonical URL", STATUS_OK if ok else STATUS_WARN, 3,
        ctx.seo.canonical_url if ok else "Could not be derived.",
    )


@register
def is_indexable(ctx: CheckContext) -> CheckResult:
    ok = ctx.seo.robots_index
    return CheckResult(
        "indexable", "Indexable", STATUS_OK if ok else STATUS_FAIL, 5,
        "Search engines may index this page."
        if ok
        else "Marked noindex -- it will not appear in search results at all.",
    )
