"""Turning an article into a per-platform caption.

Templates use ``{title}`` ``{excerpt}`` ``{link}`` ``{hashtags}``. When the
result is too long for a platform, **only the excerpt is trimmed**. That rule
is the whole design:

* trimming the link produces a broken URL, which is worse than no post;
* trimming the hashtags silently removes reach the editor asked for;
* trimming the title removes the thing the post is about.

The excerpt is the only segment where losing the tail costs nothing but detail,
so it absorbs the entire overflow, and if even an empty excerpt does not fit,
the caption is reported as impossible rather than mangled.

Trimming is done in **grapheme clusters** and on a word boundary, for the same
reason the SERP preview measures pixels: a Bengali conjunct cut in half is not
a shorter word, it is a different one.
"""

from __future__ import annotations

import re

from .constraints import counted_length, graphemes, spec_for

DEFAULT_TEMPLATE = "{title}\n\n{excerpt}\n\n{link}\n\n{hashtags}"
_WHITESPACE_RUN = re.compile(r"\n{3,}")


def render(
    template: str,
    *,
    title: str = "",
    excerpt: str = "",
    link: str = "",
    hashtags=None,
) -> str:
    tags = " ".join(
        tag if tag.startswith("#") else f"#{tag}" for tag in (hashtags or []) if tag
    )
    text = (template or DEFAULT_TEMPLATE).format(
        title=title or "", excerpt=excerpt or "", link=link or "", hashtags=tags
    )
    # An absent excerpt or empty hashtag list leaves a gap in the template;
    # collapse it rather than posting a caption with a hole in the middle.
    return _WHITESPACE_RUN.sub("\n\n", text).strip()


def truncate_graphemes(text: str, limit: int) -> str:
    """Cut to ``limit`` clusters, preferring a word boundary, adding an ellipsis."""
    # The same segmenter the counter uses. Two copies would drift, and the
    # symptom is a caption the counter says fits and the trimmer cuts anyway.
    clusters = graphemes(text)
    if limit <= 0:
        return ""
    if len(clusters) <= limit:
        return text
    cut = "".join(clusters[: max(0, limit - 1)])
    space = cut.rfind(" ")
    if space > len(cut) * 0.6:
        cut = cut[:space]
    return f"{cut.rstrip()}…"


def fit(
    template: str,
    platform: str,
    *,
    title: str = "",
    excerpt: str = "",
    link: str = "",
    hashtags=None,
) -> tuple[str, bool]:
    """Render a caption that fits ``platform``.

    Returns ``(caption, fits)``. ``fits`` is False only when the caption is
    over the limit with the excerpt removed entirely -- at which point the
    honest answer is to hand it back and let a human shorten the title, not to
    quietly cut the link in half.
    """
    spec = spec_for(platform)
    caption = render(template, title=title, excerpt=excerpt, link=link, hashtags=hashtags)
    if counted_length(caption, platform) <= spec.max_length:
        return caption, True

    without_excerpt = render(
        template, title=title, excerpt="", link=link, hashtags=hashtags
    )
    overflow_budget = spec.max_length - counted_length(without_excerpt, platform)
    if overflow_budget <= 1:
        # Even an empty excerpt does not fit. Report it rather than trimming
        # something whose truncation actually breaks the post.
        return without_excerpt, False

    trimmed = truncate_graphemes(excerpt, overflow_budget - 1)
    caption = render(template, title=title, excerpt=trimmed, link=link, hashtags=hashtags)

    # The trim is measured against the platform's own counting, which for X
    # weights URLs at 23 -- so a long link leaves *more* excerpt room than a
    # naive character count would allow.
    return caption, counted_length(caption, platform) <= spec.max_length


def derive_for_article(article, platform: str, *, link: str, template: str = "", hashtags=None):
    """Convenience wrapper: build a fitting caption from an article."""
    return fit(
        template or DEFAULT_TEMPLATE,
        platform,
        title=article.title,
        excerpt=article.excerpt,
        link=link,
        hashtags=hashtags,
    )
