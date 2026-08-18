"""Per-platform publishing rules, in one declarative table.

Every platform has its own limits and its own arithmetic, and the failure this
module exists to prevent is the two ends disagreeing about them: a composer
that says a post fits and a server that rejects it, or worse, a server that
accepts it and a platform that truncates it in public.

So this table is the single source, and it is **exported over the API** at
``GET /studio/social/platform-specs/``. The composer's counters and validators
read the same numbers the server validates against, by construction rather
than by two people remembering to update two files.

Two rules are worth calling out because they are counter-intuitive:

* **X counts every URL as 23 characters**, however long it is. A post with a
  200-character link is nowhere near the limit; a naive count says it is.
* **Length is counted in grapheme clusters, not code points.** "👨‍👩‍👧" is one
  character to a reader and five code points to Python. For the Bengali content
  this platform serves the gap is routine rather than exotic: the conjunct
  "ক্ষ" is three code points and reads as one letter.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    label: str
    #: Maximum caption length, in graphemes.
    max_length: int
    #: Length a URL counts as regardless of its real length; None = actual.
    url_length: int | None = None
    max_images: int = 4
    max_videos: int = 1
    #: Bytes.
    max_image_bytes: int = 5 * 1024 * 1024
    max_video_bytes: int = 512 * 1024 * 1024
    image_mimes: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
    video_mimes: tuple[str, ...] = ("video/mp4",)
    #: (min, max) width/height ratio the platform will accept without cropping.
    aspect_ratio_range: tuple[float, float] = (0.5, 2.0)
    #: True when publishing needs a container created first, then published --
    #: which means the provider may legitimately answer "not ready yet".
    two_step_publish: bool = False
    supports_alt_text: bool = True
    supports_scheduling: bool = False
    #: Hashtags beyond this are ignored or penalised by the platform.
    max_hashtags: int = 30
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return asdict(self)


SPECS: dict[str, PlatformSpec] = {
    "x": PlatformSpec(
        key="x",
        label="X",
        max_length=280,
        # The rule everyone gets wrong. Any link, of any length, is 23.
        url_length=23,
        max_images=4,
        max_image_bytes=5 * 1024 * 1024,
        max_video_bytes=512 * 1024 * 1024,
        aspect_ratio_range=(0.33, 3.0),
        max_hashtags=10,
        notes=("Every URL counts as 23 characters, whatever its real length.",),
    ),
    "linkedin": PlatformSpec(
        key="linkedin",
        label="LinkedIn",
        max_length=3000,
        max_images=9,
        max_image_bytes=10 * 1024 * 1024,
        max_video_bytes=200 * 1024 * 1024,
        aspect_ratio_range=(0.418, 2.4),
        notes=("Only the first ~140 characters show before “…see more”.",),
    ),
    "facebook": PlatformSpec(
        key="facebook",
        label="Facebook",
        max_length=63206,
        max_images=10,
        max_image_bytes=10 * 1024 * 1024,
        max_video_bytes=1024 * 1024 * 1024,
        aspect_ratio_range=(0.5, 1.91),
        notes=("Only the first ~250 characters show before “See more”.",),
    ),
    "threads": PlatformSpec(
        key="threads",
        label="Threads",
        max_length=500,
        max_images=10,
        max_image_bytes=8 * 1024 * 1024,
        max_video_bytes=1024 * 1024 * 1024,
        aspect_ratio_range=(0.5, 1.91),
        # Threads creates a media container first and publishes it separately;
        # the container is not immediately ready, which is why the provider
        # protocol has a "not ready, try again" answer at all.
        two_step_publish=True,
        notes=("Media is uploaded to a container, then published a moment later.",),
    ),
}

PLATFORMS = tuple(SPECS)
PLATFORM_CHOICES = tuple((key, spec.label) for key, spec in SPECS.items())


def spec_for(platform: str) -> PlatformSpec:
    try:
        return SPECS[platform]
    except KeyError:
        raise ValueError(f"Unknown platform: {platform!r}") from None


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


#: Brahmic viramas ("hasant" in Bengali). A virama binds the consonant that
#: follows it into a conjunct -- ক + ্ + ষ reads as the single letter ক্ষ --
#: which is Unicode 15.1's GB9c rule and, more to the point, what a Bengali
#: reader sees. Without it the counter tells an author their post is a third
#: longer than it looks.
_VIRAMAS = frozenset(
    "्্੍્୍்్್്්ฺ྄"
)
_ZWJ = "‍"


def graphemes(text: str) -> list[str]:
    """Split ``text`` into what a reader counts as characters.

    An approximation of UAX #29 rather than the full algorithm, which would
    need a dependency. It covers the three cases where ``len(text)`` disagrees
    with a platform's counter by enough to matter: combining marks, ZWJ emoji
    sequences, and Indic conjuncts.
    """
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    clusters: list[str] = []
    attach_next = False
    for char in text:
        code = ord(char)
        attaches = (
            attach_next
            or unicodedata.category(char) in ("Mn", "Mc", "Me")
            or unicodedata.combining(char)
            or 0xFE00 <= code <= 0xFE0F  # variation selectors
            or 0x1F3FB <= code <= 0x1F3FF  # skin-tone modifiers
        )
        # A ZWJ or a virama binds whatever comes next onto this cluster.
        attach_next = char == _ZWJ or char in _VIRAMAS

        if (attaches or char == _ZWJ) and clusters:
            clusters[-1] += char
        else:
            clusters.append(char)
    return clusters


def grapheme_length(text: str) -> int:
    """Length as a reader -- and every platform's counter -- sees it."""
    return len(graphemes(text))


def counted_length(text: str, platform: str) -> int:
    """Caption length as ``platform`` will count it."""
    spec = spec_for(platform)
    if spec.url_length is None:
        return grapheme_length(text)

    # Substitute each URL with a placeholder of the platform's fixed weight,
    # rather than subtracting -- overlapping or adjacent URLs otherwise
    # double-count the whitespace between them.
    total = 0
    cursor = 0
    for match in URL_RE.finditer(text):
        total += grapheme_length(text[cursor : match.start()])
        total += spec.url_length
        cursor = match.end()
    total += grapheme_length(text[cursor:])
    return total


def remaining(text: str, platform: str) -> int:
    return spec_for(platform).max_length - counted_length(text, platform)


def all_specs() -> list[dict]:
    return [spec.as_dict() for spec in SPECS.values()]
