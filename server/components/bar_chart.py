"""Weekly comparison bar chart.

    WOCHENVERGLEICH · KW 29-34                            DISTANZ KM
    ───────────────────────────────────────────────────────────────
          164
    128        ▓▓                    148
    ▓▓▓   ▓▓   ▓▓        ┈┈┈┈┈┈┈┈┈┈  ▓▓   ┌──┐  Ø 116 KM
    ▓▓▓   ▓▓   ▓▓   42   ▓▓          ▓▓   │88│
    ═══════════════════════════════════════════════════════════════
    KW 29 KW 30 KW 31 KW 32 KW 33 KW 34

Geometry from designWeek.png: 6 bars filling the full plot width, gap ≈ 2.5%
of that width, 2px rules above and below, value label over each bar, category
label under each. The current (in-progress) week is drawn hollow and its
category label bold.
"""
from __future__ import annotations

from typing import Callable, NamedTuple

from PIL import ImageDraw

try:
    from components.base import (
        BLACK, WHITE, draw_dashed_line, draw_tracked, draw_tracked_center,
        draw_tracked_right, font, format_number, knockout, tracked_width,
    )
except ImportError:  # running this file directly
    from base import (
        BLACK, WHITE, draw_dashed_line, draw_tracked, draw_tracked_center,
        draw_tracked_right, font, format_number, knockout, tracked_width,
    )


class BarData(NamedTuple):
    label: str
    value: float
    hollow: bool = False


TITLE_SIZE = 9
TITLE_TRACKING = 1.5
TITLE_HEIGHT = 12
TITLE_RULE_WIDTH = 2

VALUE_SIZE = 10
VALUE_TRACKING = 0.5
VALUE_HEIGHT = 15

AXIS_SIZE = 9
AXIS_TRACKING = 1.0
AXIS_HEIGHT = 20
AXIS_RULE_WIDTH = 2

AVG_SIZE = 9
AVG_TRACKING = 1.5

GAP_RATIO = 0.025
HOLLOW_OUTLINE = 2
MIN_BAR_HEIGHT = 2


def render_bar_chart(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    bars: list[BarData],
    avg_line: float | None = None,
    y_axis_label: str | None = None,
    x_axis_label: str | None = None,
    avg_label: str | None = None,
    value_format: Callable[[float], str] | None = None,
) -> None:
    """Draw a bar chart filling `box`.

    x_axis_label sits top-left (what the bars are: "WOCHENVERGLEICH · KW 29-34"),
    y_axis_label top-right (what the heights mean: "DISTANZ KM"). avg_label
    overrides the auto "Ø <value>" text next to the dashed average line.
    """
    x0, y0, x1, y1 = box
    fmt = value_format or (lambda v: format_number(v))

    # --- title row + its rule ---
    plot_top = y0
    if x_axis_label or y_axis_label:
        title_font = font(TITLE_SIZE)
        cap_top = title_font.getbbox("M")[1]
        if x_axis_label:
            draw_tracked(draw, (x0, y0 - cap_top), x_axis_label.upper(),
                         title_font, BLACK, TITLE_TRACKING)
        if y_axis_label:
            draw_tracked_right(draw, (x1, y0 - cap_top), y_axis_label.upper(),
                               title_font, BLACK, TITLE_TRACKING)
        rule_y = y0 + TITLE_HEIGHT
        draw.rectangle([x0, rule_y, x1, rule_y + TITLE_RULE_WIDTH - 1], fill=BLACK)
        plot_top = rule_y + TITLE_RULE_WIDTH + 2

    # --- baseline rule ---
    baseline = y1 - AXIS_HEIGHT
    draw.rectangle([x0, baseline, x1, baseline + AXIS_RULE_WIDTH - 1], fill=BLACK)

    if not bars:
        return

    bar_area_top = plot_top + VALUE_HEIGHT
    bar_area_h = baseline - bar_area_top
    if bar_area_h <= 0:
        return

    peak = max([b.value for b in bars] + ([avg_line] if avg_line else []) + [0.0])
    if peak <= 0:
        peak = 1.0

    n = len(bars)
    width = x1 - x0
    gap = max(4, int(round(width * GAP_RATIO)))
    bar_w = (width - gap * (n - 1)) / n

    def value_to_y(v: float) -> float:
        return baseline - (v / peak) * bar_area_h

    # --- dashed average reference, under the bars ---
    # Drawn first so bar fills and value labels sit on top of it; a dashed
    # black line over a solid black bar would be invisible anyway.
    avg_y = value_to_y(avg_line) if avg_line else None
    if avg_y is not None:
        draw_dashed_line(draw, (x0, avg_y), (x1, avg_y), BLACK, 1, dash=3, gap=4)

    # --- bars ---
    for i, bar in enumerate(bars):
        bx0 = x0 + i * (bar_w + gap)
        bx1 = bx0 + bar_w - 1
        top = value_to_y(bar.value)
        if bar.value > 0:
            top = min(top, baseline - MIN_BAR_HEIGHT)
        rect = [bx0, top, bx1, baseline - 1]

        if bar.hollow:
            draw.rectangle(rect, fill=WHITE, outline=BLACK, width=HOLLOW_OUTLINE)
        else:
            draw.rectangle(rect, fill=BLACK)

        centre = bx0 + bar_w / 2
        value_font = font(VALUE_SIZE)
        value_text = fmt(bar.value)
        value_w = tracked_width(draw, value_text, value_font, VALUE_TRACKING)
        value_top = top - VALUE_HEIGHT + 2
        cap = value_font.getbbox("M")
        # knock the label out of whatever it lands on (usually the avg line)
        knockout(draw, [centre - value_w / 2 - 2, value_top - 1,
                        centre + value_w / 2 + 2, value_top + (cap[3] - cap[1]) + 1])
        draw_tracked_center(
            draw, (centre, value_top - cap[1]),
            value_text, value_font, BLACK, VALUE_TRACKING,
        )

        axis_font = font(AXIS_SIZE, bold=bar.hollow)
        draw_tracked_center(
            draw, (centre, baseline + 8 - axis_font.getbbox("M")[1]),
            bar.label.upper(), axis_font, BLACK, AXIS_TRACKING,
        )

    # --- average label, last so nothing paints over it ---
    if avg_y is not None:
        text = avg_label if avg_label is not None else f"Ø {fmt(avg_line)}"
        avg_font = font(AVG_SIZE)
        text_w = tracked_width(draw, text.upper(), avg_font, AVG_TRACKING)
        cap = avg_font.getbbox("M")
        text_h = cap[3] - cap[1]
        label_bottom = avg_y - 3
        knockout(draw, [x1 - text_w - 4, label_bottom - text_h - 2, x1, label_bottom + 1])
        draw_tracked_right(draw, (x1, label_bottom - text_h - cap[1]),
                           text.upper(), avg_font, BLACK, AVG_TRACKING)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    img, d = demo_canvas(600, 400)

    distanz = [
        BarData("KW 29", 128), BarData("KW 30", 96), BarData("KW 31", 164),
        BarData("KW 32", 42), BarData("KW 33", 148), BarData("KW 34", 88, True),
    ]
    hoehen = [
        BarData("KW 29", 3400), BarData("KW 30", 2650), BarData("KW 31", 4980),
        BarData("KW 32", 1100), BarData("KW 33", 4320), BarData("KW 34", 2480, True),
    ]

    render_bar_chart(d, (16, 14, 584, 180), distanz, avg_line=116,
                     x_axis_label="Wochenvergleich · KW 29-34",
                     y_axis_label="Distanz km", avg_label="Ø 116 km")
    render_bar_chart(d, (16, 200, 584, 366), hoehen, avg_line=3290,
                     x_axis_label="Gleiche Wochen",
                     y_axis_label="Höhenmeter hm", avg_label="Ø 3.290 hm")

    save_preview(img, "preview_bar_chart.png")
