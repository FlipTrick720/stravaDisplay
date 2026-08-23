"""Weekly comparison view: two 6-week bar charts + a current-week sidebar.

Built directly on the components/ package (unlike activity.py and overview.py,
which are Step 1/2-era renderer.py code moved as-is - this is the first view
composed from components, per CLAUDE.md's Phase 2 plan).

Layout measured off designWeek.png:
- divider between the chart column and the sidebar sits at ~75% width
- the two bar charts split the content area evenly, each with its own
  WOCHENVERGLEICH/GLEICHE WOCHEN + DISTANZ KM/HÖHENMETER HM title row
- the footer strip ("6 WOCHEN GESAMT ...") is confined to the chart column,
  not the full canvas - the divider rule runs almost the full content height
  in the mock, past the footer row
- the sidebar has its own KW/LÄUFT bar, 3 stacked stat_blocks, then a date
  range line and an activity-count line, independent of the footer strip
"""
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

if __package__ in (None, ""):  # `python3 views/weekly.py` direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from components.bar_chart import BarData, render_bar_chart
from components.base import (
    BLACK, WHITE, draw_tracked, draw_tracked_right, font, format_number,
)
from components.header import render_header
from components.stat_block import render_stat_block

WIDTH, HEIGHT = 800, 480
HEADER_HEIGHT = 48

MARGIN_LEFT = 17
MARGIN_RIGHT = 15

DIVIDER_X = 592
SIDEBAR_X0 = 610
SIDEBAR_X1 = WIDTH - MARGIN_RIGHT

FOOTER_HEIGHT = 26
CHART_GAP = 6

KW_BAR_HEIGHT = 30
KW_BAR_PAD_X = 10

SIDEBAR_STAT_GAP = 10   # hairline rule sits in this gap, between stat blocks
SIDEBAR_BLOCK_COUNT = 3

FOOTER_LABEL = "6 WOCHEN GESAMT"


def _pct_delta(value: float, avg: float) -> str | None:
    """'-24 % GEGEN Ø'-style delta string. None if there's no average to compare to."""
    if not avg:
        return None
    delta = (value - avg) / avg * 100
    sign = "+" if delta >= 0 else "-"
    return f"{sign}{abs(delta):.0f} % gegen Ø"


def _bpm_delta(value: float | None, avg: float | None) -> str | None:
    if value is None or avg is None:
        return None
    delta = value - avg
    sign = "+" if delta >= 0 else "-"
    return f"{sign}{abs(delta):.0f} bpm gegen Ø"


def _render_kw_bar(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                    iso_week: int) -> None:
    """Small black bar: 'KW 34' left, 'LÄUFT' right. Not its own component -
    one-off enough that badge.py / header.py don't fit it cleanly."""
    x0, y0, x1, y1 = box
    draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=BLACK)
    baseline = y0 + int(round((y1 - y0) * 0.68))

    kw_font = font(14, bold=True)
    draw.text((x0 + KW_BAR_PAD_X, baseline), f"KW {iso_week}",
              font=kw_font, fill=WHITE, anchor="ls")

    laeuft_font = font(9)
    draw_tracked_right(draw, (x1 - KW_BAR_PAD_X, baseline), "LÄUFT",
                       laeuft_font, WHITE, 1.5, anchor="ls")


def _render_sidebar(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    overview,
) -> None:
    x0, y0, x1, y1 = box
    current = overview.current_week

    kw_box = (x0, y0, x1, y0 + KW_BAR_HEIGHT)
    _render_kw_bar(draw, kw_box, current.iso_week)

    stats = [
        ("DISTANZ", format_number(current.distance_m / 1000), "km",
         _pct_delta(current.distance_m, overview.avg_distance_m)),
        ("HÖHE", format_number(current.elevation_m), "hm",
         _pct_delta(current.elevation_m, overview.avg_elevation_m)),
        ("Ø PULS", format_number(current.avg_heartrate_bpm) if current.avg_heartrate_bpm else "--",
         "bpm" if current.avg_heartrate_bpm else None,
         _bpm_delta(current.avg_heartrate_bpm, overview.avg_heartrate_bpm)),
    ]

    stats_top = kw_box[3] + 16
    stats_bottom = y1 - 56  # leave room for date range + activity count below
    block_h = (stats_bottom - stats_top) / SIDEBAR_BLOCK_COUNT

    for i, (label, value, unit, delta) in enumerate(stats):
        block_y0 = stats_top + i * block_h
        block_y1 = block_y0 + block_h - SIDEBAR_STAT_GAP
        render_stat_block(draw, (x0, block_y0, x1, block_y1), label, value, unit, delta)
        if i < len(stats) - 1:
            rule_y = block_y1 + SIDEBAR_STAT_GAP / 2
            draw.line([(x0, rule_y), (x1, rule_y)], fill=BLACK, width=1)

    # --- date range + activity count, below the stats ---
    rule_y = stats_bottom
    draw.line([(x0, rule_y), (x1, rule_y)], fill=BLACK, width=1)

    small = font(9)
    date_range = (f"MO {current.start_date:%d.%m.} - "
                  f"SO {current.end_date:%d.%m.}")
    cap_top = small.getbbox("M")[1]
    draw_tracked(draw, (x0, rule_y + 8 - cap_top), date_range.upper(), small, BLACK, 1.0)

    today = datetime.now().date()
    days_elapsed = min(7, max(0, (today - current.start_date).days + 1))
    days_open = max(0, 7 - days_elapsed)
    count_text = f"{current.activity_count} AKTIVITÄTEN · {days_open} TAGE OFFEN"
    draw_tracked(draw, (x0, rule_y + 24 - cap_top), count_text, small, BLACK, 1.0)


def _render_footer(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    overview,
) -> None:
    x0, y0, x1, y1 = box
    draw.line([(x0, y0), (x1, y0)], fill=BLACK, width=1)

    small = font(9)
    cap_top = small.getbbox("M")[1]
    text_y = y0 + 8 - cap_top

    draw_tracked(draw, (x0, text_y), FOOTER_LABEL, small, BLACK, 1.5)

    summary = (
        f"{format_number(overview.total_distance_m / 1000)} KM · "
        f"{format_number(overview.total_elevation_m)} HM · "
        f"{overview.total_activities} AKTIVITÄTEN"
    )
    draw_tracked_right(draw, (x1, text_y), summary, small, BLACK, 1.5)


def render_weekly(
    overview,
    athlete_name: str,
    updated_at: datetime | None = None,
) -> Image.Image:
    """Weekly comparison view: distance + elevation bar charts, current-week
    sidebar, 6-week totals footer.

    overview: an aggregator.WeeklyOverview (weeks oldest-first, 6 entries).
    """
    img = Image.new("1", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    render_header(draw, (0, 0, WIDTH, HEADER_HEIGHT), datetime.now().year,
                  athlete_name, updated_at)

    weeks = overview.weeks
    week_range = f"KW {weeks[0].iso_week}-{weeks[-1].iso_week}"

    def bars(attr: str) -> list[BarData]:
        return [
            BarData(f"KW {w.iso_week}", getattr(w, attr), w.is_current)
            for w in weeks
        ]

    chart_x0, chart_x1 = MARGIN_LEFT, DIVIDER_X - 8
    content_y0 = HEADER_HEIGHT
    footer_y0 = HEIGHT - FOOTER_HEIGHT
    chart_area_y1 = footer_y0 - 6
    chart_h = (chart_area_y1 - content_y0 - CHART_GAP) / 2

    chart1_box = (chart_x0, content_y0 + 20, chart_x1, content_y0 + 20 + chart_h)
    chart2_box = (chart_x0, chart1_box[3] + CHART_GAP + 20,
                  chart_x1, chart_area_y1)

    render_bar_chart(
        draw, chart1_box, bars("distance_m"), avg_line=overview.avg_distance_m,
        x_axis_label=f"Wochenvergleich · {week_range}",
        y_axis_label="Distanz km",
        avg_label=f"Ø {format_number(overview.avg_distance_m / 1000)} KM",
        value_format=lambda v: format_number(v / 1000),
    )
    render_bar_chart(
        draw, chart2_box, bars("elevation_m"), avg_line=overview.avg_elevation_m,
        x_axis_label="Gleiche Wochen",
        y_axis_label="Höhenmeter hm",
        avg_label=f"Ø {format_number(overview.avg_elevation_m)} HM",
        value_format=lambda v: format_number(v),
    )

    draw.line([(DIVIDER_X, content_y0), (DIVIDER_X, footer_y0)], fill=BLACK, width=1)

    _render_sidebar(draw, (SIDEBAR_X0, content_y0 + 8, SIDEBAR_X1, HEIGHT - 8), overview)
    _render_footer(draw, (chart_x0, footer_y0, chart_x1, HEIGHT), overview)

    return img


if __name__ == "__main__":
    import aggregator

    def _week(iso_week, year, start, end, distance_km, elevation_m, hr, count, days, current):
        from datetime import date
        return aggregator.WeekStats(
            iso_week=iso_week, year=year,
            start_date=date(*start), end_date=date(*end),
            distance_m=distance_km * 1000, elevation_m=elevation_m,
            moving_time_s=count * 3600, avg_heartrate_bpm=hr,
            activity_count=count, days_with_activity=days, is_current=current,
        )

    weeks = [
        _week(29, 2026, (2026, 7, 13), (2026, 7, 19), 128, 3400, 140, 4, 3, False),
        _week(30, 2026, (2026, 7, 20), (2026, 7, 26), 96, 2650, 135, 3, 3, False),
        _week(31, 2026, (2026, 7, 27), (2026, 8, 2), 164, 4980, 145, 5, 4, False),
        _week(32, 2026, (2026, 8, 3), (2026, 8, 9), 42, 1100, 130, 2, 2, False),
        _week(33, 2026, (2026, 8, 10), (2026, 8, 16), 148, 4320, 142, 4, 3, False),
        _week(34, 2026, (2026, 8, 17), (2026, 8, 23), 88, 2480, 138, 5, 3, True),
    ]
    overview = aggregator.WeeklyOverview(
        weeks=weeks,
        current_week=weeks[-1],
        avg_distance_m=sum(w.distance_m for w in weeks[:-1]) / 5,
        avg_elevation_m=sum(w.elevation_m for w in weeks[:-1]) / 5,
        avg_heartrate_bpm=141,
        total_distance_m=sum(w.distance_m for w in weeks),
        total_elevation_m=sum(w.elevation_m for w in weeks),
        total_activities=sum(w.activity_count for w in weeks),
        date_range_start=weeks[0].start_date,
        date_range_end=weeks[-1].end_date,
    )

    img = render_weekly(overview, "Malte Braig", datetime(2026, 8, 18, 14, 35))
    out = Path(__file__).resolve().parent / "preview_weekly.png"
    img.save(out)
    print(f"wrote {out}")
