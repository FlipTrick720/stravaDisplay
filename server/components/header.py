"""Full-width black header bar shared by every view.

    2026 MALTE BRAIG                 AKTUALISIERT 19:12 · 16.08.  [STRAVA]

Geometry is taken from designActivity.png / designOverview.png / designWeek.png,
which all use the identical bar: 48px tall, text baseline at 71% of the height,
17px left inset, 15px right inset.
"""
from __future__ import annotations

from datetime import datetime

from PIL import ImageDraw

try:
    from components.badge import render_badge_inverted
    from components.base import (
        BLACK, WHITE, draw_tracked, draw_tracked_right, font,
    )
except ImportError:  # running this file directly
    from badge import render_badge_inverted
    from base import (
        BLACK, WHITE, draw_tracked, draw_tracked_right, font,
    )

PAD_LEFT = 17
PAD_RIGHT = 15
BASELINE_RATIO = 0.71

YEAR_SIZE = 24
NAME_SIZE = 14
NAME_TRACKING = 2.5
META_SIZE = 10
META_TRACKING = 2.0

YEAR_NAME_GAP = 13
META_BADGE_GAP = 16

BADGE_TEXT = "STRAVA"
BADGE_FONT_SIZE = 11
BADGE_PAD_X = 9
BADGE_PAD_Y = 7

# The task text spells the left side as "YYYY  ·  ATHLETE NAME", but all three
# mocks render year and name with no separator between them. Mocks win by
# default; set this to " · " to get the separator back.
YEAR_NAME_SEPARATOR = ""


def format_updated(updated_at: datetime) -> str:
    return f"AKTUALISIERT {updated_at:%H:%M} · {updated_at:%d.%m.}"


def render_header(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    year: int,
    athlete_name: str,
    updated_at: datetime | None = None,
) -> None:
    """Fill `box` with the black header bar."""
    x0, y0, x1, y1 = box
    height = y1 - y0
    draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=BLACK)

    baseline = y0 + int(round(height * BASELINE_RATIO))

    # --- left: year (bold) + athlete name (regular, tracked) ---
    year_font = font(YEAR_SIZE, bold=True)
    x = x0 + PAD_LEFT
    draw.text((x, baseline), str(year), font=year_font, fill=WHITE, anchor="ls")
    x += draw.textlength(str(year), font=year_font)

    name_font = font(NAME_SIZE)
    x += YEAR_NAME_GAP
    if YEAR_NAME_SEPARATOR:
        sep = YEAR_NAME_SEPARATOR.strip()
        x += draw_tracked(draw, (x, baseline), sep, name_font, WHITE,
                          NAME_TRACKING, anchor="ls") + YEAR_NAME_GAP
    draw_tracked(
        draw, (x, baseline), athlete_name.upper(),
        name_font, WHITE, NAME_TRACKING, anchor="ls",
    )

    # --- right: STRAVA badge, then the timestamp to its left ---
    badge_right = x1 - PAD_RIGHT
    badge_w, badge_h = _badge_metrics(draw)
    badge_x = badge_right - badge_w
    badge_y = y0 + (height - badge_h) // 2
    render_badge_inverted(
        draw, (badge_x, badge_y), BADGE_TEXT,
        font_size=BADGE_FONT_SIZE, pad_x=BADGE_PAD_X, pad_y=BADGE_PAD_Y,
    )

    if updated_at is not None:
        draw_tracked_right(
            draw, (badge_x - META_BADGE_GAP, baseline), format_updated(updated_at),
            font(META_SIZE), WHITE, META_TRACKING, anchor="ls",
        )


def _badge_metrics(draw: ImageDraw.ImageDraw) -> tuple[int, int]:
    try:
        from components.badge import badge_size
    except ImportError:
        from badge import badge_size
    return badge_size(
        draw, BADGE_TEXT, font_size=BADGE_FONT_SIZE,
        pad_x=BADGE_PAD_X, pad_y=BADGE_PAD_Y,
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    img, d = demo_canvas(800, 130)

    render_header(d, (0, 0, 800, 48), 2026, "Malte Braig",
                  datetime(2026, 8, 16, 19, 12))

    d.text((17, 58), "no updated_at:", font=font(11), fill=BLACK)
    render_header(d, (0, 76, 800, 124), 2025, "Ada Lovelace", None)

    save_preview(img, "preview_header.png")
