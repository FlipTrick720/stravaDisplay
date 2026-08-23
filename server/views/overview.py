"""Year overview view: 2 category panels + a full-sport-range bottom row.

Rebuilt on the components/ package (Phase 2 Step 3), replacing the Step
1/2-era code that was moved out of renderer.py as-is. First view after
weekly.py to be composed this way; activity.py is still the old style.

Layout measured off designOverview.png:
- each panel: a discrete badge (top-left) + "X / Y TRACKS" tracked text
  (top-right) at the same row, a bordered map, then a "KARTE · ..." summary
  line + rule, a "JAHR YYYY · CATEGORY" section label, then 3 stat_blocks
  side by side (DISTANZ / HÖHE / ZEIT) separated by thin vertical rules
- the mock's badge row is actually a full-width black bar, but the task
  calls for render_badge specifically - that draws a small discrete box
  instead. Structure (badge top-left, track count top-right) matches; the
  literal "full bar" treatment doesn't.
- the mock has no divider between panels (just whitespace + each panel's own
  map border); a subtle 1px vertical divider is added per this step's
  instructions, same treatment as weekly.py's chart/sidebar divider
- bottom row: left is the last activity (name + km/hm/time/vor Xd), right is
  the all-sport-YTD total - 3 stat_blocks with no separating rules, unlike
  the panel's stat row
"""
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

if __package__ in (None, ""):  # `python3 views/overview.py` direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from components.badge import render_badge
from components.base import (
    BLACK, WHITE, draw_tracked, draw_tracked_right, font, format_number,
)
from components.header import render_header
from components.map_view import render_map
from components.stat_block import render_stat_block

WIDTH, HEIGHT = 800, 480
HEADER_HEIGHT = 48

MARGIN_LEFT = 17
MARGIN_RIGHT = 15

DIVIDER_X = 400
PANEL_GAP = 16

BOTTOM_ROW_HEIGHT = 84
BOTTOM_ROW_Y0 = HEIGHT - BOTTOM_ROW_HEIGHT

PANEL_PAD_TOP = 8
GAP_AFTER_BADGE = 10
GAP_ABOVE_KARTE = 6
KARTE_LINE_H = 11
RULE_HEIGHT = 2
GAP_AFTER_RULE = 6
JAHR_LINE_H = 11
GAP_AFTER_JAHR = 8
STAT_ROW_H = 56
PANEL_STAT_VALUE_SIZE = 34

TRACKS_LABEL_SIZE = 10
TRACKS_LABEL_TRACKING = 1.5

SECTION_LABEL_SIZE = 9
SECTION_LABEL_TRACKING = 1.5

BOTTOM_LABEL_SIZE = 9
BOTTOM_LABEL_TRACKING = 1.5
ACTIVITY_NAME_SIZE = 20
ACTIVITY_SUBLINE_SIZE = 10
ACTIVITY_SUBLINE_TRACKING = 1.0
BOTTOM_STAT_VALUE_SIZE = 30
BOTTOM_STAT_COL_GAP = 12


def _time_ago_days(iso: str) -> str:
    """'VOR 2 TAGEN'-style day-granularity age, matching the mock. Same-day
    activities read 'HEUTE' rather than the odd 'VOR 0 TAGEN'."""
    start = datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    days = (datetime.now().date() - start).days
    if days <= 0:
        return "HEUTE"
    if days == 1:
        return "VOR 1 TAG"
    return f"VOR {days} TAGEN"


def _panel_box(index: int) -> tuple[int, int, int, int]:
    if index == 0:
        return (MARGIN_LEFT, HEADER_HEIGHT, DIVIDER_X - PANEL_GAP, BOTTOM_ROW_Y0)
    return (DIVIDER_X + PANEL_GAP, HEADER_HEIGHT, WIDTH - MARGIN_RIGHT, BOTTOM_ROW_Y0)


def _render_panel(draw: ImageDraw.ImageDraw, img: Image.Image,
                   box: tuple[int, int, int, int], stats, year: int) -> None:
    x0, y0, x1, y1 = box

    # --- badge + track count row ---
    badge_box = render_badge(draw, (x0, y0 + PANEL_PAD_TOP), stats.category)
    row_mid = (badge_box[1] + badge_box[3]) / 2

    tracks_font = font(TRACKS_LABEL_SIZE)
    draw_tracked_right(
        draw, (x1, row_mid), f"{len(stats.polylines)} / {stats.total_polylines} TRACKS",
        tracks_font, BLACK, TRACKS_LABEL_TRACKING, anchor="lm",
    )

    map_y0 = badge_box[3] + GAP_AFTER_BADGE

    reserved = (GAP_ABOVE_KARTE + KARTE_LINE_H + RULE_HEIGHT + GAP_AFTER_RULE
                + JAHR_LINE_H + GAP_AFTER_JAHR + STAT_ROW_H)
    map_y1 = y1 - reserved

    render_map(draw, (x0, map_y0, x1, map_y1), stats.polylines)

    # --- "KARTE · X / Y TRACKS · date range · km · hm" + rule ---
    karte_font = font(TRACKS_LABEL_SIZE)
    cap_top = karte_font.getbbox("M")[1]
    karte_y = map_y1 + GAP_ABOVE_KARTE

    if stats.shown_date_start and stats.shown_date_end:
        date_range = f"{stats.shown_date_start:%d.%m.}-{stats.shown_date_end:%d.%m.}"
        karte_text = (
            f"KARTE · {len(stats.polylines)} / {stats.total_polylines} TRACKS · "
            f"{date_range} · {format_number(stats.shown_distance_m / 1000)} KM · "
            f"{format_number(stats.shown_elevation_m)} HM"
        )
    else:
        karte_text = f"KARTE · {len(stats.polylines)} / {stats.total_polylines} TRACKS"
    draw_tracked(draw, (x0, karte_y - cap_top), karte_text, karte_font, BLACK,
                TRACKS_LABEL_TRACKING)

    rule_y = karte_y + KARTE_LINE_H
    draw.rectangle([x0, rule_y, x1, rule_y + RULE_HEIGHT - 1], fill=BLACK)

    # --- "JAHR YYYY · CATEGORY" section label ---
    jahr_y = rule_y + RULE_HEIGHT + GAP_AFTER_RULE
    section_font = font(SECTION_LABEL_SIZE)
    section_cap_top = section_font.getbbox("M")[1]
    draw_tracked(draw, (x0, jahr_y - section_cap_top),
                f"JAHR {year} · {stats.category.upper()}", section_font, BLACK,
                SECTION_LABEL_TRACKING)

    # --- 3 stat blocks, side by side, separated by thin rules ---
    stat_y0 = jahr_y + JAHR_LINE_H + GAP_AFTER_JAHR
    stat_y1 = y1
    col_w = (x1 - x0) / 3
    cols = [
        ("DISTANZ", format_number(stats.distance_m / 1000), "km"),
        ("HÖHE", format_number(stats.elevation_m), "hm"),
        ("ZEIT", _format_hours(stats.moving_time_s), "h"),
    ]
    for i, (label, value, unit) in enumerate(cols):
        col_x0 = x0 + i * col_w
        col_x1 = x0 + (i + 1) * col_w - 10
        render_stat_block(draw, (col_x0, stat_y0, col_x1, stat_y1), label, value,
                          unit, value_size=PANEL_STAT_VALUE_SIZE)
        if i > 0:
            draw.line([(col_x0 - 5, stat_y0), (col_x0 - 5, stat_y1)], fill=BLACK, width=1)


def _format_hours(seconds: int) -> str:
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}:{m:02d}"


def _render_bottom_left(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                         activity: dict) -> None:
    x0, y0, x1, y1 = box

    label_font = font(BOTTOM_LABEL_SIZE)
    cap_top = label_font.getbbox("M")[1]
    draw_tracked(draw, (x0, y0 - cap_top), "LETZTE AKTIVITÄT", label_font, BLACK,
                BOTTOM_LABEL_TRACKING)

    name_font = font(ACTIVITY_NAME_SIZE, bold=True)
    name = activity["name"]
    max_width = x1 - x0
    while draw.textlength(name, font=name_font) > max_width and len(name) > 10:
        name = name[:-1]
    if name != activity["name"]:
        name = name.rstrip() + "…"
    draw.text((x0, y0 + 14), name, font=name_font, fill=BLACK)

    subline_font = font(ACTIVITY_SUBLINE_SIZE)
    subline_cap_top = subline_font.getbbox("M")[1]
    subline = (
        f"{format_number(activity['distance'] / 1000, 1)} KM · "
        f"{format_number(activity.get('total_elevation_gain', 0))} HM · "
        f"{_format_hours(activity.get('moving_time', 0))} H · "
        f"{_time_ago_days(activity['start_date_local'])}"
    )
    draw_tracked(draw, (x0, y0 + 40 - subline_cap_top), subline, subline_font, BLACK,
                ACTIVITY_SUBLINE_TRACKING)


def _render_bottom_right(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                          overview) -> None:
    x0, y0, x1, y1 = box

    label_font = font(BOTTOM_LABEL_SIZE)
    cap_top = label_font.getbbox("M")[1]
    draw_tracked(draw, (x0, y0 - cap_top), f"JAHR {overview.year} · ALLE SPORTARTEN",
                label_font, BLACK, BOTTOM_LABEL_TRACKING)

    footer_font = font(BOTTOM_LABEL_SIZE)
    footer_cap_top = footer_font.getbbox("M")[1]
    footer_y = y1 - footer_cap_top

    stats = [
        format_number(overview.year_total_distance_m / 1000),
        format_number(overview.year_total_elevation_m),
        _format_hours(overview.year_total_time_s),
    ]
    units = ["km", "hm", "h"]
    stat_y0 = y0 + 14
    stat_y1 = footer_y - 14
    col_w = (x1 - x0) / 3
    for i, (value, unit) in enumerate(zip(stats, units)):
        col_x0 = x0 + i * col_w
        col_x1 = col_x0 + col_w - BOTTOM_STAT_COL_GAP
        render_stat_block(draw, (col_x0, stat_y0, col_x1, stat_y1), "", value, unit,
                          value_size=BOTTOM_STAT_VALUE_SIZE)

    footer = (f"{overview.year_total_activities} AKTIVITÄTEN · "
              f"SEIT {overview.date_range_start_of_year:%d.%m.%Y}")
    draw_tracked(draw, (x0, footer_y), footer, footer_font, BLACK,
                BOTTOM_LABEL_TRACKING)


def render_overview(
    overview,
    athlete_name: str,
    updated_at: datetime | None = None,
) -> Image.Image:
    """Year overview: 2 most-recently-used category panels + all-sport totals.

    overview: an aggregator.Overview.
    """
    img = Image.new("1", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    render_header(draw, (0, 0, WIDTH, HEADER_HEIGHT), overview.year, athlete_name,
                  updated_at)

    for i in range(min(2, len(overview.categories))):
        _render_panel(draw, img, _panel_box(i), overview.categories[i], overview.year)

    draw.line([(DIVIDER_X, HEADER_HEIGHT), (DIVIDER_X, BOTTOM_ROW_Y0)], fill=BLACK, width=1)

    draw.rectangle([0, BOTTOM_ROW_Y0, WIDTH, BOTTOM_ROW_Y0 + 1], fill=BLACK)

    bottom_y0 = BOTTOM_ROW_Y0 + 12
    _render_bottom_left(draw, (MARGIN_LEFT, bottom_y0, DIVIDER_X - PANEL_GAP, HEIGHT - 6),
                        overview.last_activity)
    _render_bottom_right(draw, (DIVIDER_X + PANEL_GAP, bottom_y0, WIDTH - MARGIN_RIGHT, HEIGHT - 6),
                         overview)

    return img


if __name__ == "__main__":
    import aggregator

    import math
    from datetime import date

    def _cat(category, count, distance_km, elevation_m, hours, polylines,
              total_polylines, shown_km, shown_hm, shown_start, shown_end):
        return aggregator.CategoryStats(
            category=category, count=count, distance_m=distance_km * 1000,
            elevation_m=elevation_m, moving_time_s=int(hours * 3600),
            polylines=polylines, total_polylines=total_polylines,
            shown_distance_m=shown_km * 1000, shown_elevation_m=shown_hm,
            shown_date_start=date(*shown_start), shown_date_end=date(*shown_end),
        )

    def _fake_track(lat0, lon0, heading_deg, scale, n=60):
        import polyline as pl
        heading = math.radians(heading_deg)
        pts = [
            (lat0 + scale * (i / n) * math.cos(heading) + scale * 0.15 * math.sin(i / n * 3 * math.pi),
             lon0 + scale * (i / n) * math.sin(heading) + scale * 0.15 * math.cos(i / n * 3 * math.pi))
            for i in range(n)
        ]
        return pl.encode(pts)

    # A few fabricated tracks around Innsbruck so cities/compass/scale render.
    fake_polylines = [
        _fake_track(47.26, 11.38, 70, 0.22),
        _fake_track(47.25, 11.40, 100, 0.18),
        _fake_track(47.27, 11.35, 40, 0.20),
    ]

    categories = [
        _cat("MTB", 62, 1284, 38910, 96 + 20 / 60, fake_polylines, 62,
             486, 14400, (2026, 7, 27), (2026, 8, 14)),
        _cat("Ski", 6, 104, 7640, 18 + 5 / 60, fake_polylines[:2], 6,
             104, 7640, (2026, 1, 6), (2026, 3, 2)),
    ]

    overview = aggregator.Overview(
        year=2026,
        categories=categories,
        last_activity={
            "name": "Nockspitze Feierabendrunde",
            "distance": 42100,
            "total_elevation_gain": 980,
            "moving_time": 2 * 3600 + 48 * 60,
            "start_date": "2026-08-16T17:04:00Z",
            "start_date_local": "2026-08-16T17:04:00Z",
        },
        year_total_distance_m=1512 * 1000,
        year_total_elevation_m=48930,
        year_total_time_s=122 * 3600 + 40 * 60,
        year_total_activities=75,
        date_range_start_of_year=date(2026, 1, 1),
    )

    img = render_overview(overview, "Malte Braig", datetime(2026, 8, 18, 14, 35))
    out = Path(__file__).resolve().parent / "preview_overview.png"
    img.save(out)
    print(f"wrote {out}")
