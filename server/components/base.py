"""Shared drawing primitives for the component library.

Not a component itself. Holds the font handling, letter-spaced text and the
small formatting helpers every component needs, so the six render_* modules
stay free of duplicated boilerplate.

All components draw 1-bit: fill=BLACK (0) or fill=WHITE (1).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Hardcoded on purpose: the Dockerfile installs fonts-dejavu-core for exactly
# this path and the Pi has it too. Changing it breaks both.
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

BLACK = 0
WHITE = 1

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Cached DejaVu Sans / DejaVu Sans Bold at the given pixel size."""
    key = (size, bold)
    if key not in _FONT_CACHE:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        _FONT_CACHE[key] = ImageFont.truetype(f"{FONT_DIR}/{name}", size)
    return _FONT_CACHE[key]


# =========================
# Letter-spaced ("tracked") text
# =========================
#
# The design language leans on wide-tracked uppercase micro labels
# (AKTUALISIERT, DISTANZ, KW 29). PIL has no tracking, so we place glyph by
# glyph. Measured against the mocks: ~2px at size 10, ~1px at size 9.

def tracked_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    tracking: float = 1.5,
) -> float:
    """Width of `text` when drawn by draw_tracked with the same tracking."""
    if not text:
        return 0.0
    return sum(draw.textlength(c, font=fnt) for c in text) + tracking * (len(text) - 1)


def draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: int = BLACK,
    tracking: float = 1.5,
    anchor: str = "la",
) -> float:
    """Draw letter-spaced text, left-anchored at xy. Returns the width drawn.

    `anchor` must be left-horizontal ("l..") because glyphs are positioned
    individually; only its vertical half ("a" top, "s" baseline, "m" middle)
    actually varies.
    """
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=fnt) + tracking
    return max(0.0, x - xy[0] - tracking)


def draw_tracked_right(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: int = BLACK,
    tracking: float = 1.5,
    anchor: str = "la",
) -> float:
    """Like draw_tracked but xy is the RIGHT edge of the text."""
    w = tracked_width(draw, text, fnt, tracking)
    draw_tracked(draw, (xy[0] - w, xy[1]), text, fnt, fill, tracking, anchor)
    return w


def draw_tracked_center(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: int = BLACK,
    tracking: float = 1.5,
    anchor: str = "la",
) -> float:
    """Like draw_tracked but xy is the horizontal CENTER of the text."""
    w = tracked_width(draw, text, fnt, tracking)
    draw_tracked(draw, (xy[0] - w / 2, xy[1]), text, fnt, fill, tracking, anchor)
    return w


# =========================
# Metrics
# =========================

def cap_height(fnt: ImageFont.FreeTypeFont) -> int:
    """Ink height of a digit. Digits sit on the baseline, so this doubles as
    the baseline offset from an "la" (ascender-top) origin."""
    box = fnt.getbbox("0")
    return box[3] - box[1]


def baseline_offset(fnt: ImageFont.FreeTypeFont) -> int:
    """Distance from an "la" origin down to the baseline."""
    return fnt.getbbox("0")[3]


def ink_top_offset(fnt: ImageFont.FreeTypeFont) -> int:
    """Distance from an "la" origin down to the top of a digit's ink."""
    return fnt.getbbox("0")[1]


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: float,
    size: int,
    bold: bool = True,
    min_size: int = 8,
) -> ImageFont.FreeTypeFont:
    """Largest font <= `size` whose `text` fits in max_width. Shrinks only."""
    while size > min_size:
        fnt = font(size, bold)
        if draw.textlength(text, font=fnt) <= max_width:
            return fnt
        size -= 1
    return font(min_size, bold)


# =========================
# Lines
# =========================

def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p0: tuple[float, float],
    p1: tuple[float, float],
    fill: int = BLACK,
    width: int = 1,
    dash: int = 4,
    gap: int = 4,
) -> None:
    """Dashed straight line. Used for average references and the pulse curve."""
    x0, y0 = p0
    x1, y1 = p1
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length <= 0:
        return
    dx = (x1 - x0) / length
    dy = (y1 - y0) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        draw.line(
            [(x0 + dx * pos, y0 + dy * pos), (x0 + dx * end, y0 + dy * end)],
            fill=fill,
            width=width,
        )
        pos = end + gap


def draw_dashed_path(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: int = BLACK,
    width: int = 1,
    dash: int = 4,
    gap: int = 4,
) -> None:
    """Dashed polyline: walks the path at constant arc length so the dash
    rhythm stays even across segments of different lengths."""
    if len(points) < 2:
        return
    carry = 0.0      # distance already consumed inside the current dash/gap
    drawing = True
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        seg = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if seg <= 0:
            continue
        dx = (x1 - x0) / seg
        dy = (y1 - y0) / seg
        pos = 0.0
        while pos < seg:
            span = (dash if drawing else gap) - carry
            end = min(pos + span, seg)
            if drawing:
                draw.line(
                    [(x0 + dx * pos, y0 + dy * pos), (x0 + dx * end, y0 + dy * end)],
                    fill=fill,
                    width=width,
                )
            consumed = end - pos
            if consumed >= span:
                drawing = not drawing
                carry = 0.0
            else:
                carry += consumed
            pos = end


def knockout(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    fill: int = WHITE,
) -> None:
    """Clear a rectangle so text stays legible over a line or a chart."""
    draw.rectangle(box, fill=fill)


# =========================
# Formatting
# =========================

def format_number(value: float, decimals: int = 0) -> str:
    """German number formatting: 4980 -> '4.980', 42.05 -> '42,1' (1 decimal)."""
    text = f"{value:,.{decimals}f}"
    # en -> de: swap separators via a placeholder so the two passes don't collide
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# =========================
# Smoke-test helpers
# =========================

def demo_canvas(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """1-bit white canvas, matching the e-paper panel's mode."""
    img = Image.new("1", (width, height), WHITE)
    return img, ImageDraw.Draw(img)


def save_preview(img: Image.Image, name: str) -> Path:
    """Write a component preview next to the component module."""
    path = Path(__file__).resolve().parent / name
    img.save(path)
    print(f"wrote {path}")
    return path
