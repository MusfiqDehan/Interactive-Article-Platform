#!/usr/bin/env python3
"""Render the Storyloom product intro to marketing/storyloom-intro.mp4.

Picture matches the marketing theme (paper, ink, terracotta) and the app
primary blue used for interactive UI. Narration is synthesized, then muxed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "marketing"
PUBLIC_DIR = ROOT / "frontend" / "public" / "marketing"
BUILD = Path("/tmp/storyloom-intro-build")
W, H = 1920, 1080
FPS = 30

# Landing theme + app primary (primary-600 / primary-50 / primary-700).
BG = (250, 249, 246)
INK = (37, 41, 35)
MUTED = (110, 113, 105)
LINE = (225, 227, 218)
ACCENT = (195, 84, 48)
SOFT = (240, 241, 234)
CARD = (255, 255, 255)
FOREST = (38, 62, 53)
CREAM = (247, 242, 231)
SAGE = (193, 207, 189)
TERR = (233, 151, 114)
PRIMARY = (37, 99, 235)
PRIMARY_DARK = (29, 78, 216)
PRIMARY_SOFT = (239, 246, 255)
PRIMARY_LINE = (191, 219, 254)
WHITE = (255, 255, 255)
SKY = (230, 217, 187)
SUN = (238, 178, 120)
MOUNT_BACK = (169, 180, 156)
MOUNT_FRONT = (88, 110, 96)

SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_ITALIC = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SANS = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"
SANS_MED = "/usr/share/fonts/truetype/lato/Lato-Medium.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"
BN_SERIF = "/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf"
MONO = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"

VOICE = "en-US-AndrewNeural"
RATE = "-4%"

# Spoken lines. Same scene name = no fade between them.
CUES = [
    ("open", "name", "Storyloom."),
    ("open", "tagline", "A new dimension to every story."),
    ("problem", "pain", "Flat pages lose readers. The context that makes a story matter never gets a chance."),
    ("blocks", "blocks", "Writers compose in blocks. Text, images, audio, and video, together in one editor."),
    ("interact", "interact", "Annotations, image hotspots, and media chapters keep curiosity on the page."),
    ("reader", "reader", "Readers open a source, explore a photograph, or jump to the moment that matters."),
    ("impact", "impact", "Time with the story goes up. The narrative stays intact. The desk moves faster."),
    ("workflow", "workflow", "One workspace takes a draft through review, and out to the web."),
    ("discover", "discover", "Search previews, social cards, and sitemaps bring the right people in."),
    ("bilingual", "bilingual", "English and Bangla, side by side, with room for both scripts."),
    ("close", "close", "From first draft to final discovery. Stories worth reading, and exploring."),
]

CHAPTERS = [
    ("open", "A new dimension", "নতুন মাত্রা"),
    ("problem", "Flat pages", "সমতল পাতা"),
    ("blocks", "Compose in blocks", "ব্লকে সাজান"),
    ("interact", "On the page", "একই পাতায়"),
    ("reader", "Readers stay", "পাঠক থাকে"),
    ("impact", "Business impact", "ব্যবসায়িক প্রভাব"),
    ("workflow", "Draft to publish", "ড্রাফট থেকে প্রকাশ"),
    ("discover", "Made to be found", "খুঁজে পাওয়ার যোগ্য"),
    ("bilingual", "English and Bangla", "ইংরেজি ও বাংলা"),
    ("close", "Start your story", "গল্প শুরু করুন"),
]

LABELS = {
    "open": "INTRO",
    "problem": "THE PROBLEM",
    "blocks": "THE EDITOR",
    "interact": "INTERACTIVE",
    "reader": "THE READER",
    "impact": "IMPACT",
    "workflow": "THE STUDIO",
    "discover": "DISCOVERY",
    "bilingual": "TWO LANGUAGES",
    "close": "STORYLOOM",
}

_FONTS: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_SHADOWS: dict[tuple, Image.Image] = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(path, size)
    return _FONTS[key]


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def ease(v: float) -> float:
    v = clamp(v)
    return 1 - (1 - v) ** 3


def rise(enter: float, index: int, gap: float = 0.1) -> tuple[float, int]:
    e = ease(clamp((enter - index * gap) / 0.55))
    return e, int((1 - e) * 42)


def shadow(w: int, h: int, radius: int = 22) -> tuple[Image.Image, int]:
    blur = 18
    key = (w, h, radius, blur)
    if key not in _SHADOWS:
        pad = blur * 3
        im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((pad, pad + 8, pad + w, pad + 8 + h), radius, fill=(*FOREST, 38))
        _SHADOWS[key] = im.filter(ImageFilter.GaussianBlur(blur))
    return _SHADOWS[key], 18 * 3


def panel(base: Image.Image, box: tuple[int, int, int, int], radius: int = 22, fill: tuple = CARD, outline: tuple = LINE) -> None:
    x0, y0, x1, y1 = [int(v) for v in box]
    sprite, pad = shadow(x1 - x0, y1 - y0, radius)
    base.alpha_composite(sprite, (x0 - pad, y0 - pad))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x0, y0, x1, y1), radius, fill=fill + (255,), outline=outline + (255,), width=2)


def text(d: ImageDraw.ImageDraw, xy, value, face, fill, anchor="lt") -> None:
    d.text(xy, value, font=face, fill=fill + (255,), anchor=anchor)


def tracked(d, xy, value, face, fill, tracking=1.8, anchor="lt") -> float:
    widths = [face.getlength(ch) for ch in value]
    total = sum(widths) + tracking * max(0, len(value) - 1)
    x, y = xy
    if anchor.startswith("m"):
        x -= total / 2
    elif anchor.startswith("r"):
        x -= total
    for ch, wch in zip(value, widths):
        d.text((x, y), ch, font=face, fill=fill + (255,))
        x += wch + tracking
    return total


def mark(base: Image.Image, cx: float, cy: float, size: float) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y, s = cx - size / 2, cy - size / 2, size

    def p(px, py):
        return (x + px / 64 * s, y + py / 64 * s)

    r = max(8, int(s * 17 / 64))
    d.rounded_rectangle((x, y, x + s, y + s), r, fill=FOREST + (255,))
    d.polygon([p(13, 20), p(22, 18), p(32, 25), p(32, 48), p(21, 44), p(13, 43)], fill=CREAM + (255,))
    d.polygon([p(32, 25), p(43, 18), p(51, 19), p(51, 44), p(42, 45), p(32, 49)], fill=SAGE + (255,))
    d.polygon([p(32, 25), p(39, 15), p(47, 11), p(47, 36), p(39, 42), p(32, 49)], fill=TERR + (255,))
    ccx, ccy = p(49, 43)
    rad = 7 / 64 * s
    d.ellipse((ccx - rad, ccy - rad, ccx + rad, ccy + rad), fill=CREAM + (255,), outline=FOREST + (255,), width=max(2, int(s / 28)))
    arm = 2.6 / 64 * s
    width = max(2, int(s / 26))
    d.line((ccx - arm, ccy, ccx + arm, ccy), fill=ACCENT + (255,), width=width)
    d.line((ccx, ccy - arm, ccx, ccy + arm), fill=ACCENT + (255,), width=width)
    base.alpha_composite(layer)


def paint_landscape(base: Image.Image, box, radius: int = 16, hotspot: bool = False, corners: str = "all") -> None:
    x0, y0, x1, y1 = [int(v) for v in box]
    width, height = x1 - x0, y1 - y0
    tile = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    landscape(ImageDraw.Draw(tile), (0, 0, width, height), hotspot=hotspot)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=255)
    if corners == "top":
        ImageDraw.Draw(mask).rectangle((0, height - radius - 1, width, height), fill=255)
    tile.putalpha(mask)
    base.alpha_composite(tile, (x0, y0))


def landscape(d: ImageDraw.ImageDraw, box, hotspot=False) -> None:
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=SKY + (255,))
    sun_r = (y1 - y0) * 0.16
    sx, sy = x0 + (x1 - x0) * 0.68, y0 + (y1 - y0) * 0.22
    d.ellipse((sx - sun_r, sy - sun_r, sx + sun_r, sy + sun_r), fill=SUN + (255,))
    h = y1 - y0
    back = [
        (x0, y1), (x0, y0 + h * 0.72), (x0 + (x1 - x0) * 0.12, y0 + h * 0.48),
        (x0 + (x1 - x0) * 0.28, y0 + h * 0.66), (x0 + (x1 - x0) * 0.46, y0 + h * 0.18),
        (x0 + (x1 - x0) * 0.66, y0 + h * 0.7), (x0 + (x1 - x0) * 0.82, y0 + h * 0.36),
        (x1, y0 + h * 0.68), (x1, y1),
    ]
    front = [
        (x0, y1), (x0, y0 + h * 0.9), (x0 + (x1 - x0) * 0.2, y0 + h * 0.48),
        (x0 + (x1 - x0) * 0.4, y0 + h * 0.78), (x0 + (x1 - x0) * 0.58, y0 + h * 0.46),
        (x0 + (x1 - x0) * 0.75, y0 + h * 0.74), (x0 + (x1 - x0) * 0.9, y0 + h * 0.32),
        (x1, y0 + h * 0.5), (x1, y1),
    ]
    d.polygon(back, fill=MOUNT_BACK + (255,))
    d.polygon(front, fill=MOUNT_FRONT + (255,))
    text(d, (x0 + 16, y1 - 28), "27°59′ N    86°55′ E", font(MONO, 14), WHITE)
    if hotspot:
        hx, hy = x0 + (x1 - x0) * 0.62, y0 + h * 0.42
        d.ellipse((hx - 22, hy - 22, hx + 22, hy + 22), fill=PRIMARY + (255,))
        d.line((hx - 9, hy, hx + 9, hy), fill=WHITE + (255,), width=3)
        d.line((hx, hy - 9, hx, hy + 9), fill=WHITE + (255,), width=3)


def eyebrow(d, xy, label: str) -> None:
    x, y = xy
    d.rounded_rectangle((x, y + 4, x + 8, y + 12), 1, fill=ACCENT + (255,))
    tracked(d, (x + 18, y), label, font(SANS_BOLD, 15), MUTED, tracking=2.4)


def headline(d, xy, value: str, size=68) -> None:
    x, y = xy
    face = font(SERIF, size)
    for i, line in enumerate(value.split("\n")):
        text(d, (x, y + i * (size + 8)), line, face, INK)


def chrome(base: Image.Image, scene: str, progress: float) -> None:
    d = ImageDraw.Draw(base)
    d.rectangle((0, 0, int(W * clamp(progress)), 6), fill=PRIMARY + (255,))
    mark(base, 108, 58, 40)
    text(d, (138, 46), "Storyloom", font(SANS_BOLD, 22), INK)
    tracked(d, (W - 84, 50), LABELS[scene], font(SANS_BOLD, 14), MUTED, tracking=2.2, anchor="rt")
    d.line((0, 968, W, 968), fill=LINE + (255,), width=2)


def caption(base: Image.Image, value: str, opacity: float) -> None:
    if opacity < 0.04 or not value:
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((84, 996, 96, 1008), 2, fill=PRIMARY + (255,))
    face = font(SANS_MED, 26)
    words = value.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if face.getlength(trial) <= 1500:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines[:2]):
        text(d, (112, 986 + i * 34), line, face, INK)
    r, g, b, a = layer.split()
    a = a.point(lambda v: int(v * opacity))
    layer.putalpha(a)
    base.alpha_composite(layer)


def draw_open(base, beat, enter) -> None:
    e, dy = rise(enter, 0, 0)
    if e <= 0:
        return
    mark(base, W / 2, 390 + dy, 150)
    d = ImageDraw.Draw(base)
    text(d, (W / 2, 520 + dy), "Storyloom", font(SERIF, 92), INK, anchor="mt")
    if beat == "tagline":
        e2, dy2 = rise(enter, 1, 0.05)
        if e2 > 0:
            text(d, (W / 2, 630 + dy2), "A new dimension to every story.", font(SERIF_ITALIC, 36), ACCENT, anchor="mt")
            tracked(d, (W / 2, 700 + dy2), "BILINGUAL PUBLISHING STUDIO", font(SANS_BOLD, 15), PRIMARY, tracking=3.2, anchor="mt")


def draw_problem(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 168 + dy), "THE PROBLEM")
        headline(d, (88, 210 + dy), "Flat pages\nlose readers.")
        body = font(SANS, 24)
        text(d, (88, 400 + dy), "Readers skim, leave, and miss the context", body, MUTED)
        text(d, (88, 434 + dy), "that makes a story matter.", body, MUTED)
    chips = [("Skimmed", SOFT, MUTED), ("Left the page", (253, 236, 232), ACCENT), ("Context lost", (253, 236, 232), ACCENT)]
    for i, (label, bg, fg) in enumerate(chips):
        e2, dy2 = rise(enter, 2 + i)
        if e2 <= 0:
            continue
        x = 88 + i * 230
        y = 520 + dy2
        d.rounded_rectangle((x, y, x + 210, y + 54), 27, fill=bg + (255,))
        text(d, (x + 105, y + 27), label, font(SANS_BOLD, 18), fg, anchor="mm")
    e3, dy3 = rise(enter, 1)
    if e3 <= 0:
        return
    box = (1040, 175 + dy3, 1832, 900 + dy3)
    panel(base, box)
    d = ImageDraw.Draw(base)
    paint_landscape(base, (1042, 177 + dy3, 1830, 430 + dy3), radius=20, corners="top")
    text(d, (1072, 456 + dy3), "NATURE  ·  A FLAT PAGE", font(SANS_BOLD, 14), ACCENT)
    text(d, (1072, 490 + dy3), "A story with nowhere to go.", font(SERIF, 32), INK)
    y = 560 + dy3
    for width in (680, 640, 700, 520):
        d.rounded_rectangle((1072, y, 1072 + width, y + 14), 7, fill=SOFT + (255,))
        y += 32
    d.rounded_rectangle((1072, 760 + dy3, 1560, 840 + dy3), 16, outline=ACCENT + (255,), width=2)
    text(d, (1316, 800 + dy3), "The aside never opens", font(SANS_MED, 20), ACCENT, anchor="mm")


def draw_blocks(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 150 + dy), "COMPOSE")
        headline(d, (88, 190 + dy), "Every format, one story.", size=64)
    cards = [
        ("Text", "The argument, set in blocks."),
        ("Image", "A photograph that can hold more."),
        ("Audio", "A voice, with room to breathe."),
        ("Video", "A film the reader can navigate."),
    ]
    gap, width = 22, 425
    for i, (title, body) in enumerate(cards):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        x = 84 + i * (width + gap)
        y = 360 + dy2
        panel(base, (x, y, x + width, y + 520))
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((x + 28, y + 28, x + 70, y + 36), 3, fill=PRIMARY + (255,))
        text(d, (x + 28, y + 48), f"0{i + 1}", font(SANS_BOLD, 16), PRIMARY)
        text(d, (x + 28, y + 78), title, font(SERIF, 40), INK)
        text(d, (x + 28, y + 136), body, font(SANS, 20), MUTED)
        art = (x + 28, y + 210, x + width - 28, y + 470)
        if i == 0:
            d.rounded_rectangle(art, 14, fill=SOFT + (255,))
            text(d, (art[0] + 24, art[1] + 28), "A better story", font(SERIF, 28), INK)
            for n, wline in enumerate((280, 250, 300, 180)):
                d.rounded_rectangle((art[0] + 24, art[1] + 90 + n * 28, art[0] + 24 + wline, art[1] + 104 + n * 28), 6, fill=LINE + (255,))
        elif i == 1:
            paint_landscape(base, art, radius=14)
        elif i == 2:
            d.rounded_rectangle(art, 14, fill=FOREST + (255,))
            mid = (art[1] + art[3]) / 2
            bars = [28, 48, 70, 40, 90, 56, 76, 36, 64, 44, 80, 30]
            for n, bh in enumerate(bars):
                bx = art[0] + 28 + n * 28
                d.rounded_rectangle((bx, mid - bh / 2, bx + 14, mid + bh / 2), 6, fill=PRIMARY + (255,))
        else:
            d.rounded_rectangle(art, 14, fill=FOREST + (255,))
            cx, cy = (art[0] + art[2]) / 2, (art[1] + art[3]) / 2
            d.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=PRIMARY + (255,))
            d.polygon([(cx - 12, cy - 18), (cx - 12, cy + 18), (cx + 20, cy)], fill=WHITE + (255,))


def draw_interact(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 150 + dy), "ON THE PAGE")
        headline(d, (88, 190 + dy), "Curiosity stays on the page.", size=60)
    cards = [
        ("Annotation", "A phrase opens a source,\nwithout sending anyone away."),
        ("Hotspot", "A point on the picture\nholds a second story."),
        ("Chapters", "Readers jump to the\nmoment that matters."),
    ]
    width = 573
    for i, (title, body) in enumerate(cards):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        x = 84 + i * (width + 20)
        y = 360 + dy2
        panel(base, (x, y, x + width, y + 530))
        d = ImageDraw.Draw(base)
        d.rectangle((x + 28, y + 28, x + 36, y + 58), fill=PRIMARY + (255,))
        text(d, (x + 52, y + 28), title, font(SERIF, 36), INK)
        for n, line in enumerate(body.split("\n")):
            text(d, (x + 28, y + 100 + n * 32), line, font(SANS, 22), MUTED)
        if i == 0:
            d.rounded_rectangle((x + 28, y + 210, x + width - 28, y + 470), 16, fill=PRIMARY_SOFT + (255,))
            text(d, (x + 52, y + 250), "Look closer at the", font(SANS, 24), INK)
            phrase = "stories beneath"
            text(d, (x + 52, y + 292), phrase, font(SANS_BOLD, 24), PRIMARY_DARK)
            pw = font(SANS_BOLD, 24).getlength(phrase)
            d.line((x + 52, y + 326, x + 52 + pw, y + 326), fill=PRIMARY + (255,), width=3)
            text(d, (x + 52, y + 360), "Opens a note, a source, a definition.", font(SANS, 18), PRIMARY_DARK)
        elif i == 1:
            paint_landscape(base, (x + 28, y + 210, x + width - 28, y + 470), radius=14, hotspot=True)
        else:
            for n, (stamp, label) in enumerate([("00:00", "The journey"), ("02:14", "A new perspective"), ("04:02", "Looking closer")]):
                cy = y + 230 + n * 78
                on = n == 1
                d.rounded_rectangle((x + 28, cy, x + width - 28, cy + 64), 14, fill=(PRIMARY_SOFT if on else SOFT) + (255,))
                d.ellipse((x + 46, cy + 16, x + 78, cy + 48), fill=(PRIMARY if on else FOREST) + (255,))
                d.polygon([(x + 58, cy + 24), (x + 58, cy + 40), (x + 72, cy + 32)], fill=WHITE + (255,))
                text(d, (x + 96, cy + 18), stamp, font(MONO, 16), PRIMARY if on else MUTED)
                text(d, (x + 180, cy + 16), label, font(SANS_BOLD, 20), INK)


def draw_reader(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 168 + dy), "THE USE")
        headline(d, (88, 210 + dy), "Go deeper,\nwithout leaving.")
    steps = [
        ("01", "Open a source", "An annotation answers the question on the same page."),
        ("02", "Explore a photograph", "A hotspot ties a place in the image to more reporting."),
        ("03", "Jump to the moment", "Chapters turn a film into a story the reader can steer."),
    ]
    for i, (num, title, body) in enumerate(steps):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        y = 470 + i * 150 + dy2
        d.ellipse((88, y, 156, y + 68), fill=PRIMARY + (255,))
        text(d, (122, y + 34), num, font(SANS_BOLD, 20), WHITE, anchor="mm")
        if i < 2:
            d.rectangle((118, y + 68, 126, y + 150), fill=PRIMARY_LINE + (255,))
        text(d, (188, y + 4), title, font(SERIF, 36), INK)
        text(d, (188, y + 56), body, font(SANS, 22), MUTED)
    e3, dy3 = rise(enter, 2)
    if e3 <= 0:
        return
    panel(base, (1180, 200 + dy3, 1836, 900 + dy3))
    d = ImageDraw.Draw(base)
    text(d, (1220, 240 + dy3), "WHO IT'S FOR", font(SANS_BOLD, 14), MUTED)
    uses = [
        ("Journals", "Long-form reporting that rewards a closer look."),
        ("Newsrooms", "Desks that publish, review, and update together."),
        ("Bilingual teams", "English and Bangla in one editorial studio."),
    ]
    for i, (title, body) in enumerate(uses):
        y = 300 + dy3 + i * 180
        d.rounded_rectangle((1220, y, 1272, y + 52), 12, fill=PRIMARY_SOFT + (255,))
        text(d, (1246, y + 26), f"0{i + 1}", font(SANS_BOLD, 18), PRIMARY, anchor="mm")
        text(d, (1292, y + 8), title, font(SANS_BOLD, 26), INK)
        for n, line in enumerate(wrap(body, font(SANS, 20), 480)):
            text(d, (1292, y + 52 + n * 28), line, font(SANS, 20), MUTED)


def wrap(value: str, face, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in value.split():
        trial = word if not cur else f"{cur} {word}"
        if face.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_impact(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 150 + dy), "BUSINESS IMPACT")
        headline(d, (88, 190 + dy), "What changes for the desk.", size=60)
    cards = [
        ("In-page context", "Sources and asides open where the reader already is, so the story keeps them."),
        ("Longer sessions", "Hotspots and chapters give a reason to stay through the piece."),
        ("A faster desk", "Authors, editors, and admins share one review path instead of a side channel."),
        ("Wider discovery", "Search previews, social cards, and sitemaps leave with the story."),
    ]
    width, gap = 425, 22
    for i, (title, body) in enumerate(cards):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        x = 84 + i * (width + gap)
        y = 380 + dy2
        panel(base, (x, y, x + width, y + 430))
        d = ImageDraw.Draw(base)
        d.ellipse((x + 28, y + 32, x + 92, y + 96), fill=PRIMARY + (255,))
        text(d, (x + 60, y + 64), f"0{i + 1}", font(SANS_BOLD, 20), WHITE, anchor="mm")
        text(d, (x + 28, y + 130), title, font(SERIF, 34), INK)
        for n, line in enumerate(wrap(body, font(SANS, 22), width - 56)):
            text(d, (x + 28, y + 210 + n * 32), line, font(SANS, 22), MUTED)


def draw_workflow(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 160 + dy), "THE STUDIO")
        headline(d, (88, 200 + dy), "A clear path to publish.", size=64)
    steps = [
        ("Write", "Author", "A blank page of blocks."),
        ("Enrich", "Interactive", "Notes, hotspots, chapters."),
        ("Review", "Editor", "A queue with clear roles."),
        ("Publish", "The desk", "Search, social, and date."),
    ]
    for i, (title, role, body) in enumerate(steps):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        x = 120 + i * 450
        y = 430 + dy2
        d.ellipse((x, y, x + 72, y + 72), fill=(PRIMARY if i == 3 else FOREST) + (255,))
        text(d, (x + 36, y + 36), f"0{i + 1}", font(SANS_BOLD, 20), WHITE, anchor="mm")
        if i < 3:
            d.rectangle((x + 72, y + 32, x + 400, y + 40), fill=PRIMARY_LINE + (255,))
        text(d, (x, y + 100), title, font(SERIF, 40), INK)
        text(d, (x, y + 160), role.upper(), font(SANS_BOLD, 15), PRIMARY)
        text(d, (x, y + 196), body, font(SANS, 22), MUTED)
    e3, _ = rise(enter, 5)
    if e3 > 0:
        tracked(d, (W / 2, 820), "JOURNALS    ·    NEWSROOMS    ·    BILINGUAL DESKS", font(SANS_BOLD, 16), MUTED, tracking=1.6, anchor="mt")


def draw_discover(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 150 + dy), "DISCOVERY")
        headline(d, (88, 190 + dy), "Made to be found.", size=64)
    width = 573
    titles = ["Search preview", "Social card", "Sitemap"]
    for i, title in enumerate(titles):
        e2, dy2 = rise(enter, i + 1)
        if e2 <= 0:
            continue
        x = 84 + i * (width + 20)
        y = 370 + dy2
        panel(base, (x, y, x + width, y + 510))
        d = ImageDraw.Draw(base)
        text(d, (x + 28, y + 28), title.upper(), font(SANS_BOLD, 14), MUTED)
        if i == 0:
            d.rounded_rectangle((x + 28, y + 80, x + width - 28, y + 140), 20, fill=SOFT + (255,))
            text(d, (x + 52, y + 98), "stories worth reading", font(SANS, 22), MUTED)
            text(d, (x + 28, y + 180), "A little closer to the extraordinary", font(SANS_BOLD, 26), PRIMARY)
            text(d, (x + 28, y + 230), "meridian / field-notes", font(SANS, 18), ACCENT)
            for n, line in enumerate(wrap("Search preview, title, and description prepared before the story goes live.", font(SANS, 20), width - 64)):
                text(d, (x + 28, y + 290 + n * 30), line, font(SANS, 20), MUTED)
        elif i == 1:
            paint_landscape(base, (x + 28, y + 80, x + width - 28, y + 300), radius=14)
            text(d, (x + 28, y + 324), "Stories worth reading.", font(SERIF, 30), INK)
            text(d, (x + 28, y + 380), "And exploring.", font(SERIF_ITALIC, 26), ACCENT)
            text(d, (x + 28, y + 440), "STORYLOOM", font(SANS_BOLD, 14), MUTED)
        else:
            rows = ["/articles", "/categories", "/articles/field-notes", "/sitemap.xml"]
            for n, row in enumerate(rows):
                yy = y + 100 + n * 80
                d.rounded_rectangle((x + 28, yy, x + width - 28, yy + 60), 12, fill=SOFT + (255,))
                d.ellipse((x + 48, yy + 20, x + 68, yy + 40), fill=PRIMARY + (255,))
                text(d, (x + 88, yy + 16), row, font(MONO, 20), INK)


def draw_bilingual(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0)
    if e > 0:
        eyebrow(d, (88, 150 + dy), "TWO LANGUAGES")
        headline(d, (88, 190 + dy), "No compromise.", size=64)
    e1, dy1 = rise(enter, 1)
    e2, dy2 = rise(enter, 2)
    if e1 > 0:
        panel(base, (84, 380 + dy1, 940, 860 + dy1))
        d = ImageDraw.Draw(base)
        text(d, (140, 430 + dy1), "ENGLISH", font(SANS_BOLD, 16), PRIMARY)
        text(d, (140, 500 + dy1), "Aa", font(SERIF, 160), INK)
        text(d, (140, 720 + dy1), "Native type. Unicode links.", font(SANS, 26), MUTED)
    if e2 > 0:
        panel(base, (980, 380 + dy2, 1836, 860 + dy2))
        d = ImageDraw.Draw(base)
        text(d, (1040, 430 + dy2), "বাংলা", font(BN_SERIF, 28), ACCENT)
        text(d, (1040, 520 + dy2), "অ আ", font(BN_SERIF, 140), INK)
        text(d, (1040, 740 + dy2), "একই স্টুডিও। একই গল্প।", font(BN_SERIF, 28), MUTED)


def draw_close(base, _beat, enter) -> None:
    d = ImageDraw.Draw(base)
    e, dy = rise(enter, 0, 0)
    if e <= 0:
        return
    mark(base, W / 2, 300 + dy, 108)
    text(d, (W / 2, 400 + dy), "Stories worth reading.", font(SERIF, 64), INK, anchor="mt")
    e2, dy2 = rise(enter, 1)
    if e2 > 0:
        text(d, (W / 2, 490 + dy2), "And exploring.", font(SERIF_ITALIC, 64), ACCENT, anchor="mt")
    e3, dy3 = rise(enter, 2)
    if e3 > 0:
        bw, bh = 360, 68
        x0, y0 = (W - bw) / 2, 620 + dy3
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 10, fill=PRIMARY + (255,))
        text(d, (W / 2, y0 + bh / 2), "Start your story", font(SANS_BOLD, 22), WHITE, anchor="mm")
        tracked(d, (W / 2, 740 + dy3), "FROM FIRST DRAFT TO FINAL DISCOVERY", font(SANS_BOLD, 15), MUTED, tracking=2.6, anchor="mt")


SCENES = {
    "open": draw_open,
    "problem": draw_problem,
    "blocks": draw_blocks,
    "interact": draw_interact,
    "reader": draw_reader,
    "impact": draw_impact,
    "workflow": draw_workflow,
    "discover": draw_discover,
    "bilingual": draw_bilingual,
    "close": draw_close,
}


def render_frame(state: dict) -> Image.Image:
    base = Image.new("RGBA", (W, H), BG + (255,))
    scene = state["scene"]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    SCENES[scene](layer, state["beat"], state["enter"])
    opacity = state["opacity"]
    if opacity < 0.999:
        r, g, b, a = layer.split()
        a = a.point(lambda v: int(v * opacity))
        layer.putalpha(a)
    base.alpha_composite(layer)
    chrome(base, scene, state["progress"])
    caption(base, state["caption"], state["caption_opacity"])
    return base


def state_at(t: float, timeline: list[dict], total: float) -> dict:
    progress = t / total if total else 0
    lead = timeline[0]["t0"]
    if t < lead:
        return {
            "scene": "open", "beat": "name", "enter": ease(t / max(lead, 0.01)),
            "opacity": clamp(t / 0.35), "caption": "", "caption_opacity": 0, "progress": progress,
        }
    for i, cue in enumerate(timeline):
        if cue["t0"] <= t < cue["t1"]:
            return {
                "scene": cue["scene"], "beat": cue["beat"],
                "enter": clamp((t - cue["t0"]) / 0.7),
                "opacity": 1, "caption": cue["text"], "caption_opacity": 1, "progress": progress,
            }
        nxt = timeline[i + 1] if i + 1 < len(timeline) else None
        if nxt and cue["t1"] <= t < nxt["t0"]:
            gap = nxt["t0"] - cue["t1"]
            u = (t - cue["t1"]) / gap if gap else 1
            if cue["scene"] == nxt["scene"]:
                cap_out = cue["text"] if u < 0.5 else nxt["text"]
                return {
                    "scene": cue["scene"], "beat": cue["beat"] if u < 0.5 else nxt["beat"],
                    "enter": 1, "opacity": 1, "caption": cap_out,
                    "caption_opacity": 1 - abs(u - 0.5) * 1.2, "progress": progress,
                }
            if u < 0.55:
                return {
                    "scene": cue["scene"], "beat": cue["beat"], "enter": 1,
                    "opacity": clamp(1 - (u / 0.55)), "caption": cue["text"],
                    "caption_opacity": clamp(1 - u * 2), "progress": progress,
                }
            return {
                "scene": nxt["scene"], "beat": nxt["beat"], "enter": clamp((u - 0.55) / 0.45),
                "opacity": clamp((u - 0.55) / 0.45), "caption": nxt["text"],
                "caption_opacity": clamp((u - 0.6) / 0.4), "progress": progress,
            }
    last = timeline[-1]
    return {
        "scene": last["scene"], "beat": last["beat"], "enter": 1, "opacity": 1,
        "caption": "", "caption_opacity": 0, "progress": progress,
    }


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as handle:
        return handle.getnframes() / handle.getframerate()


def silence(path: Path, seconds: float) -> None:
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(path),
    ])


def to_wav(src: Path, dst: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


async def synthesize() -> None:
    import edge_tts

    BUILD.mkdir(parents=True, exist_ok=True)
    for scene, beat, line in CUES:
        key = hashlib.sha1(f"{VOICE}|{RATE}|{line}".encode()).hexdigest()[:12]
        mp3 = BUILD / f"{key}.mp3"
        if not mp3.exists() or mp3.stat().st_size < 1000:
            last_error: Exception | None = None
            for attempt in range(5):
                try:
                    await edge_tts.Communicate(line, VOICE, rate=RATE).save(str(mp3))
                    if mp3.stat().st_size >= 1000:
                        last_error = None
                        break
                except Exception as exc:  # transient TTS failures
                    last_error = exc
                    if mp3.exists():
                        mp3.unlink()
                    await asyncio.sleep(3 * (attempt + 1))
            if last_error or not mp3.exists():
                raise SystemExit(f"TTS failed for {line!r}: {last_error}")
            await asyncio.sleep(1.5)
        wav = BUILD / f"{key}.wav"
        if not wav.exists():
            to_wav(mp3, wav)


def build_timeline() -> tuple[list[dict], float, Path]:
    timeline = []
    pieces: list[Path] = []
    t = 0.55
    lead = BUILD / "lead.wav"
    silence(lead, t)
    pieces.append(lead)
    for i, (scene, beat, line) in enumerate(CUES):
        key = hashlib.sha1(f"{VOICE}|{RATE}|{line}".encode()).hexdigest()[:12]
        wav = BUILD / f"{key}.wav"
        dur = wav_duration(wav)
        timeline.append({"scene": scene, "beat": beat, "text": line, "t0": t, "t1": t + dur})
        pieces.append(wav)
        t += dur
        if i < len(CUES) - 1:
            gap = 0.18 if CUES[i + 1][0] == scene else 0.32
        else:
            gap = 1.35
        gap_path = BUILD / f"gap-{i}.wav"
        silence(gap_path, gap)
        pieces.append(gap_path)
        t += gap
    concat = BUILD / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in pieces), encoding="utf-8")
    master = BUILD / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(master)])
    return timeline, t, master


def write_chapters(timeline: list[dict]) -> None:
    starts = {}
    for cue in timeline:
        starts.setdefault(cue["scene"], round(cue["t0"], 2))
    payload = [
        {"id": scene, "title": title, "titleBn": title_bn, "t": starts[scene]}
        for scene, title, title_bn in CHAPTERS
    ]
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for folder in (OUT_DIR, PUBLIC_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "chapters.json").write_text(text, encoding="utf-8")


def encode(timeline: list[dict], total: float, audio: Path, preview: bool) -> None:
    frames = int(round(total * FPS))
    if preview:
        sheet = Image.new("RGB", (W, len(timeline) * 270), BG)
        for i, cue in enumerate(timeline):
            snap = render_frame(state_at(min(cue["t0"] + 0.85, cue["t1"] - 0.05), timeline, total)).convert("RGB")
            snap.thumbnail((480, 270))
            sheet.paste(snap, (0, i * 270))
            snap.save(BUILD / f"frame-{i:02d}-{cue['scene']}.png")
        sheet.save(BUILD / "contact-sheet.png")
        poster = render_frame(state_at(timeline[-1]["t0"] + 0.9, timeline, total)).convert("RGB")
        for folder in (OUT_DIR, PUBLIC_DIR):
            folder.mkdir(parents=True, exist_ok=True)
            poster.save(folder / "storyloom-intro-poster.jpg", quality=90)
        print(f"preview frames in {BUILD}")
        return

    out = OUT_DIR / "storyloom-intro.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-i", str(audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-metadata", "title=Storyloom — A new dimension to every story",
        "-shortest", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for n in range(frames):
            frame = render_frame(state_at(n / FPS, timeline, total)).convert("RGB")
            proc.stdin.write(frame.tobytes())
            if n % FPS == 0:
                print(f"frame {n}/{frames}", flush=True)
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode() if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(err[-4000:])
    poster = render_frame(state_at(timeline[-1]["t0"] + 0.9, timeline, total)).convert("RGB")
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    poster.save(OUT_DIR / "storyloom-intro-poster.jpg", quality=90)
    poster.save(PUBLIC_DIR / "storyloom-intro-poster.jpg", quality=90)
    shutil.copy2(out, PUBLIC_DIR / "storyloom-intro.mp4")
    print(f"wrote {out} and {PUBLIC_DIR / 'storyloom-intro.mp4'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    asyncio.run(synthesize())
    timeline, total, audio = build_timeline()
    write_chapters(timeline)
    print(f"duration {total:.2f}s")
    for cue in timeline:
        print(f"  {cue['t0']:6.2f}  {cue['scene']:10}  {cue['text']}")
    encode(timeline, total, audio, args.preview)


if __name__ == "__main__":
    main()
