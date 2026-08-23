"""One statistic: small tracked label, big bold number, inline unit, optional delta.

    DISTANZ                 KW 34 sidebar variant adds the delta line:
    42,1 KM                     88 KM
                                -24 % GEGEN Ø

Sizes measured off designActivity.png's right column (value ~40px, unit ~13px,
label 9px) and its sub-stat row (value 32px, unit 9px), so the unit tracks the
value size at ~0.30 and the caller only ever picks `value_size`.
"""
from __future__ import annotations

from PIL import ImageDraw

try:
    from components.base import (
        BLACK, baseline_offset, draw_tracked, fit_font, font, ink_top_offset,
        tracked_width,
    )
except ImportError:  # running this file directly
    from base import (
        BLACK, baseline_offset, draw_tracked, fit_font, font, ink_top_offset,
        tracked_width,
    )

LABEL_SIZE = 9
LABEL_TRACKING = 1.0
VALUE_SIZE = 40
UNIT_RATIO = 0.30
UNIT_GAP = 2
DELTA_SIZE = 9
DELTA_TRACKING = 1.0

LABEL_TO_VALUE_GAP = 6
VALUE_TO_DELTA_GAP = 9


def render_stat_block(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    unit: str | None = None,
    delta: str | None = None,
    value_size: int = VALUE_SIZE,
    label_size: int = LABEL_SIZE,
    unit_size: int | None = None,
) -> None:
    """Draw label/value/unit/delta stacked at the top-left of `box`.

    The value shrinks (never grows) if value+unit would overflow the box width.

    unit_size overrides the unit's auto-scaled size (value_size * UNIT_RATIO,
    which shrinks below legibility for small value_size - e.g. a heart glyph
    next to a small KUDOS count). Leave it None for the normal km/hm/bpm case.
    """
    x0, y0, x1, y1 = box
    width = x1 - x0

    # --- label ---
    label_font = font(label_size)
    label_cap = label_font.getbbox("M")
    draw_tracked(
        draw, (x0, y0 - label_cap[1]), label.upper(),
        label_font, BLACK, LABEL_TRACKING,
    )
    label_bottom = y0 + (label_cap[3] - label_cap[1])

    # --- value + unit, sharing one baseline ---
    unit_text = unit.upper() if unit else ""
    auto_unit_size = unit_size if unit_size is not None else max(8, int(round(value_size * UNIT_RATIO)))
    reserved = 0.0
    if unit_text:
        reserved = tracked_width(draw, unit_text, font(auto_unit_size, bold=True), 0.5) + UNIT_GAP

    value_font = fit_font(draw, value, width - reserved, value_size, bold=True)
    value_top = label_bottom + LABEL_TO_VALUE_GAP
    baseline = value_top - ink_top_offset(value_font) + baseline_offset(value_font)

    draw.text((x0, baseline), value, font=value_font, fill=BLACK, anchor="ls")
    x = x0 + draw.textlength(value, font=value_font)

    if unit_text:
        # unit size follows the value's *actual* size after any shrink, unless
        # the caller pinned an explicit size
        if unit_size is None:
            auto_unit_size = max(8, int(round(value_font.size * UNIT_RATIO)))
        draw_tracked(
            draw, (x + UNIT_GAP, baseline), unit_text,
            font(auto_unit_size, bold=True), BLACK, 0.5, anchor="ls",
        )

    # --- delta ---
    if delta:
        delta_font = font(DELTA_SIZE)
        draw_tracked(
            draw, (x0, baseline + VALUE_TO_DELTA_GAP - delta_font.getbbox("M")[1]),
            delta.upper(), delta_font, BLACK, DELTA_TRACKING,
        )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    img, d = demo_canvas(620, 260)

    # designActivity.png right column
    d.line([(10, 10), (10, 250)], fill=BLACK, width=2)
    render_stat_block(d, (24, 16, 210, 76), "DISTANZ", "42,1", "km")
    d.line([(24, 78), (200, 78)], fill=BLACK, width=1)
    render_stat_block(d, (24, 84, 210, 144), "HÖHE", "980", "hm")
    d.line([(24, 146), (200, 146)], fill=BLACK, width=1)
    render_stat_block(d, (24, 152, 210, 212), "ZEIT", "2:48", "h")

    # designWeek.png sidebar variant, with delta
    render_stat_block(d, (250, 16, 420, 100), "DISTANZ", "88", "km",
                      delta="-24 % gegen Ø")
    render_stat_block(d, (250, 116, 420, 200), "HÖHE", "2.480", "hm",
                      delta="-25 % gegen Ø")

    # designActivity.png sub-stat row: smaller value, no delta
    render_stat_block(d, (450, 16, 600, 60), "Ø PULS", "142", "bpm", value_size=32)
    render_stat_block(d, (450, 76, 600, 120), "KALORIEN", "1.980", "kcal",
                      value_size=32)
    # overflow case: shrinks to fit instead of spilling out of the box
    d.rectangle([450, 136, 599, 200], outline=BLACK, width=1)
    render_stat_block(d, (452, 140, 598, 198), "ENG", "123.456", "km")

    save_preview(img, "preview_stat_block.png")
