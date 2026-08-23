"""Small rectangular category badge (MTB, SKI, STRAVA, ...).

Auto-sizes to its text. Unlike the render_X(draw, box, data) components this
one is positioned by its top-left corner and returns the box it claimed, so a
caller can lay out whatever comes next beside it.
"""
from __future__ import annotations

from PIL import ImageDraw

try:
    from components.base import (
        BLACK, WHITE, draw_tracked, font, tracked_width,
    )
except ImportError:  # running this file directly
    from base import BLACK, WHITE, draw_tracked, font, tracked_width

FONT_SIZE = 10
TRACKING = 1.0
PAD_X = 6
PAD_Y = 5


def badge_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_size: int = FONT_SIZE,
    tracking: float = TRACKING,
    pad_x: int = PAD_X,
    pad_y: int = PAD_Y,
) -> tuple[int, int]:
    """(width, height) render_badge would occupy. For right-aligned layouts."""
    fnt = font(font_size, bold=True)
    w = tracked_width(draw, text.upper(), fnt, tracking)
    cap = fnt.getbbox("M")[3] - fnt.getbbox("M")[1]
    return int(round(w + 2 * pad_x)), int(cap + 2 * pad_y)


def render_badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    filled: bool = True,
    font_size: int = FONT_SIZE,
    tracking: float = TRACKING,
    pad_x: int = PAD_X,
    pad_y: int = PAD_Y,
) -> tuple[int, int, int, int]:
    """Draw a badge with its top-left corner at xy. Returns (x0, y0, x1, y1).

    filled=True  black block, white text  (category badge on white ground)
    filled=False white block, black border and text (badge on a black bar)
    """
    text = text.upper()
    fnt = font(font_size, bold=True)
    w, h = badge_size(draw, text, font_size, tracking, pad_x, pad_y)
    x0, y0 = xy
    x1, y1 = x0 + w - 1, y0 + h - 1

    if filled:
        draw.rectangle([x0, y0, x1, y1], fill=BLACK)
        ink = WHITE
    else:
        draw.rectangle([x0, y0, x1, y1], fill=WHITE, outline=BLACK, width=1)
        ink = BLACK

    cap_top = fnt.getbbox("M")[1]
    draw_tracked(draw, (x0 + pad_x, y0 + pad_y - cap_top), text, fnt, ink, tracking)
    return (x0, y0, x1, y1)


def render_badge_inverted(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    **kwargs,
) -> tuple[int, int, int, int]:
    """Badge for a black background: white 1px border, no fill, white text.

    This is the STRAVA badge in the header bar; `filled` cannot express it
    because both of its variants assume a white ground.
    """
    text = text.upper()
    font_size = kwargs.pop("font_size", FONT_SIZE)
    tracking = kwargs.pop("tracking", TRACKING)
    pad_x = kwargs.pop("pad_x", PAD_X)
    pad_y = kwargs.pop("pad_y", PAD_Y)
    fnt = font(font_size, bold=True)
    w, h = badge_size(draw, text, font_size, tracking, pad_x, pad_y)
    x0, y0 = xy
    x1, y1 = x0 + w - 1, y0 + h - 1

    draw.rectangle([x0, y0, x1, y1], outline=WHITE, width=1)
    cap_top = fnt.getbbox("M")[1]
    draw_tracked(draw, (x0 + pad_x, y0 + pad_y - cap_top), text, fnt, WHITE, tracking)
    return (x0, y0, x1, y1)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    img, d = demo_canvas(420, 150)

    d.text((12, 10), "filled=True", font=font(11), fill=BLACK)
    x = 12
    for cat in ["MTB", "SKI", "ROAD", "HIKE"]:
        box = render_badge(d, (x, 30), cat)
        x = box[2] + 10

    d.text((12, 60), "filled=False", font=font(11), fill=BLACK)
    x = 12
    for cat in ["MTB", "SKI", "ROAD", "HIKE"]:
        box = render_badge(d, (x, 80), cat, filled=False)
        x = box[2] + 10

    # inverted variant needs a black ground to be visible
    d.rectangle([0, 108, 419, 149], fill=BLACK)
    render_badge_inverted(d, (12, 118), "STRAVA", font_size=11, pad_x=9, pad_y=7)
    render_badge_inverted(d, (110, 118), "KW 34", font_size=11, pad_x=9, pad_y=7)

    save_preview(img, "preview_badge.png")
