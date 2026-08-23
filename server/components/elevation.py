"""Elevation profile with an optional heart-rate overlay.

    HÖHENPROFIL                            MAX 1.940 M · MIN 610 M
         ╭─╮  ┈┈┈╭╮┈┈                                        PULS
    ╭────╯ ╰──╯  ╰──╮                                        HÖHE
    ──0 KM────────────────21 KM──────────────────────────────────

Solid line = altitude, dashed = heart rate (own min/max, so both curves use the
full plot height). Matches the bottom chart of designActivity.png.
"""
from __future__ import annotations

from PIL import ImageDraw

try:
    from components.base import (
        BLACK, draw_dashed_path, draw_tracked, draw_tracked_right, font,
        format_number, knockout, tracked_width,
    )
except ImportError:  # running this file directly
    from base import (
        BLACK, draw_dashed_path, draw_tracked, draw_tracked_right, font,
        format_number, knockout, tracked_width,
    )

TITLE_SIZE = 9
TITLE_TRACKING = 1.5
TITLE_HEIGHT = 14

AXIS_SIZE = 9
AXIS_TRACKING = 1.5
AXIS_HEIGHT = 14

SERIES_LABEL_SIZE = 8
SERIES_LABEL_TRACKING = 1.0
SERIES_LABEL_WIDTH = 34

ALTITUDE_WIDTH = 2
HEARTRATE_WIDTH = 1

TITLE = "HÖHENPROFIL"
ALTITUDE_LABEL = "HÖHE"
HEARTRATE_LABEL = "PULS"


def render_elevation(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    altitude_stream: list[float],
    distance_stream: list[float],
    heartrate_stream: list[float] | None = None,
    fill_area: bool = False,
    title: str | None = TITLE,
) -> None:
    """Draw the profile filling `box`.

    altitude_stream and distance_stream are Strava streams of equal length
    (distance in metres, ascending). heartrate_stream, if given, must match
    that length too.
    """
    x0, y0, x1, y1 = box

    plot_x0 = x0
    plot_x1 = x1 - SERIES_LABEL_WIDTH
    plot_y0 = y0 + TITLE_HEIGHT
    plot_y1 = y1 - AXIS_HEIGHT
    plot_w = int(plot_x1 - plot_x0)
    plot_h = plot_y1 - plot_y0

    usable = (
        altitude_stream and distance_stream
        and len(altitude_stream) >= 2
        and len(distance_stream) == len(altitude_stream)
        and plot_w > 4 and plot_h > 4
    )

    title_font = font(TITLE_SIZE)
    cap_top = title_font.getbbox("M")[1]
    if title:
        draw_tracked(draw, (x0, y0 - cap_top), title.upper(),
                     title_font, BLACK, TITLE_TRACKING)

    if not usable:
        draw_tracked(draw, (x0, plot_y0 + 8), "HÖHENPROFIL: N/A",
                     font(11), BLACK, 1.0)
        return

    alt_min, alt_max = min(altitude_stream), max(altitude_stream)
    draw_tracked_right(
        draw, (x1, y0 - cap_top),
        f"MAX {format_number(alt_max)} M · MIN {format_number(alt_min)} M",
        title_font, BLACK, TITLE_TRACKING,
    )

    dist_max = distance_stream[-1] or 1.0

    def resample(stream: list[float]) -> list[tuple[float, float]]:
        """One point per pixel column, nearest sample by distance."""
        lo, hi = min(stream), max(stream)
        span = (hi - lo) or 1.0
        pts = []
        idx = 0
        for px in range(plot_w + 1):
            target = (px / plot_w) * dist_max
            while idx + 1 < len(distance_stream) and distance_stream[idx + 1] < target:
                idx += 1
            value = stream[min(idx, len(stream) - 1)]
            pts.append((plot_x0 + px, plot_y1 - (value - lo) / span * plot_h))
        return pts

    alt_points = resample(altitude_stream)

    if fill_area:
        draw.polygon(alt_points + [(plot_x1, plot_y1), (plot_x0, plot_y1)], fill=BLACK)
    else:
        draw.line(alt_points, fill=BLACK, width=ALTITUDE_WIDTH)

    hr_points = None
    if heartrate_stream and len(heartrate_stream) == len(altitude_stream):
        hr_points = resample(heartrate_stream)
        draw_dashed_path(draw, hr_points, BLACK, HEARTRATE_WIDTH, dash=4, gap=3)

    # --- series labels at the right edge, at each curve's end height ---
    label_font = font(SERIES_LABEL_SIZE)
    label_cap = label_font.getbbox("M")
    label_h = label_cap[3] - label_cap[1]

    labels: list[tuple[str, float]] = []
    if hr_points:
        labels.append((HEARTRATE_LABEL, hr_points[-1][1] - label_h / 2))
    labels.append((ALTITUDE_LABEL, alt_points[-1][1] - label_h / 2))

    # Both curves can end at nearly the same height; push the labels apart so
    # the lower one does not knock the upper one out.
    labels.sort(key=lambda item: item[1])
    spacing = label_h + 5
    for i in range(1, len(labels)):
        text, y = labels[i]
        labels[i] = (text, max(y, labels[i - 1][1] + spacing))
    shift = max(0.0, labels[-1][1] + label_h - plot_y1)
    for i, (text, y) in enumerate(labels):
        labels[i] = (text, max(plot_y0, y - shift))

    for text, y in labels:
        knockout(draw, [plot_x1 + 1, y - 2, x1, y + label_h + 2])
        draw_tracked(draw, (plot_x1 + 4, y - label_cap[1]), text,
                     label_font, BLACK, SERIES_LABEL_TRACKING)
        draw.line([(plot_x1 + 4, y + label_h + 1), (x1, y + label_h + 1)],
                  fill=BLACK, width=1)

    # --- x axis: rule with the 0 and total-distance marks knocked out ---
    axis_y = plot_y1 + 6
    draw.line([(x0, axis_y), (x1, axis_y)], fill=BLACK, width=1)

    axis_font = font(AXIS_SIZE)
    axis_cap = axis_font.getbbox("M")
    axis_h = axis_cap[3] - axis_cap[1]

    def axis_mark(text: str, cx: float, align_left: bool = False) -> None:
        w = tracked_width(draw, text, axis_font, AXIS_TRACKING)
        left = cx if align_left else cx - w / 2
        knockout(draw, [left - 4, axis_y - axis_h / 2 - 3,
                        left + w + 4, axis_y + axis_h / 2 + 3])
        draw_tracked(draw, (left, axis_y - axis_h / 2 - axis_cap[1]),
                     text, axis_font, BLACK, AXIS_TRACKING)

    axis_mark("0 KM", x0 + 2, align_left=True)
    axis_mark(f"{format_number(dist_max / 1000)} KM", (plot_x0 + plot_x1) / 2)


if __name__ == "__main__":
    import math
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    n = 400
    distance = [i / (n - 1) * 21000 for i in range(n)]
    altitude = [
        610 + 1330 * (0.5 - 0.5 * math.cos(i / n * 2.4 * math.pi)) ** 1.2
        + 40 * math.sin(i / 9)
        for i in range(n)
    ]
    heartrate = [
        128 + 30 * (0.5 - 0.5 * math.cos((i + 55) / n * 2.3 * math.pi))
        + 5 * math.sin(i / 40)
        for i in range(n)
    ]

    img, d = demo_canvas(800, 230)

    render_elevation(d, (14, 10, 786, 100), altitude, distance, heartrate)

    d.line([(14, 110), (786, 110)], fill=BLACK, width=1)
    render_elevation(d, (14, 124, 786, 200), altitude, distance,
                     fill_area=True, title="Höhenprofil (gefüllt, ohne Puls)")

    save_preview(img, "preview_elevation.png")
