"""Activity detail view: single-track map + stats + elevation profile.

Rebuilt on the components/ package (Phase 2 Step 4), replacing the Step
1/2-era code that was moved out of renderer.py as-is. Last of the three
views to be composed this way (weekly.py in Step 2, overview.py in Step 3).

Layout measured off designActivity.png:
- header (48px, components.header) - sub-header row (58px: LETZTE AKTIVITÄT
  + name on the left, category badge + weekday date on the right, no
  separating rule against the header) - a full-width rule, then the main
  content block (map + 4 stacked stat_blocks on the right, sub-stats row
  below the map only, bottom-aligned with the stat column) - a full-width
  rule - the elevation profile filling the rest
- the map column is ~65% width per this step's instructions (the mock's own
  ratio is closer to ~72%, but 65/35 leaves the stat column enough room for
  "42,1 KM"-sized text without being cramped)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polyline as pl
from PIL import Image, ImageDraw

if __package__ in (None, ""):  # `python3 views/activity.py` direct execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aggregator
from components.badge import badge_size, render_badge
from components.base import (
    BLACK, WHITE, draw_tracked, font, format_number, tracked_width,
)
from components.elevation import render_elevation
from components.header import render_header
from components.map_view import MapMarker, render_map
from components.stat_block import render_stat_block

WIDTH, HEIGHT = 800, 480
HEADER_HEIGHT = 48
SUBHEADER_HEIGHT = 58
MAIN_CONTENT_Y1 = 366  # header + subheader + main content = 48 + 58 + 260
ELEVATION_Y0 = MAIN_CONTENT_Y1

MARGIN_LEFT = 17
MARGIN_RIGHT = 15

MAP_COLUMN_X1 = 530          # ~65% of 800
STAT_COLUMN_X0 = 546

SUBSTATS_HEIGHT = 47          # bottom band of the left column, under the map
SUBSTATS_Y1 = MAIN_CONTENT_Y1
SUBSTATS_Y0 = SUBSTATS_Y1 - SUBSTATS_HEIGHT

STAT_ROW_COUNT = 4
SUB_STAT_VALUE_SIZE = 26
SUB_STAT_COL_GAP = 10

SUBHEADER_LABEL_SIZE = 9
SUBHEADER_LABEL_TRACKING = 1.5
ACTIVITY_NAME_SIZE = 22
DATE_LABEL_SIZE = 10
DATE_LABEL_TRACKING = 1.5

WEEKDAY_DE = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]  # date.weekday(): Mon=0

KUDOS_HEART = "❤"  # U+2764, confirmed to render as a filled heart in DejaVu Sans

# Round-trip marker handling: if start/end fall within this fraction of the
# track's own bounding box, they're close enough to be visually the same
# point (a filled disc under a hollow square would erase the disc). Nudging
# by a fraction of the box's span keeps both markers visible at any zoom
# level without needing to replicate render_map's pixel projection here.
ROUND_TRIP_THRESHOLD = 0.05
ROUND_TRIP_OFFSET = 0.035


def _parse_local(iso: str) -> datetime:
    """start_date_local carries local wall-clock numbers with a 'Z' suffix -
    a documented Strava API quirk. Never convert its timezone, just read the
    fields off it (matches aggregator._local_date's convention)."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _format_duration_short(seconds: int) -> str:
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}:{m:02d}"


def _display_name(name: str) -> str:
    """Title-case an all-caps name; leave already mixed-case names alone."""
    return name.title() if name.isupper() else name


def _hr_value(activity: dict, key: str) -> tuple[str, str | None]:
    value = activity.get(key)
    return (format_number(value), "bpm") if value else ("-", None)


def _calories_value(activity: dict) -> tuple[str, str | None]:
    calories = activity.get("calories")
    return (format_number(calories), "kcal") if calories is not None else ("-", None)


def _prepare_markers(points: list[tuple[float, float]], start_label: str,
                      ziel_label: str) -> list[MapMarker]:
    """START/ZIEL markers, nudging ZIEL apart from START for a round trip."""
    start_lat, start_lon = points[0]
    end_lat, end_lon = points[-1]

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lat_span = max(lats) - min(lats) or 0.001
    lon_span = max(lons) - min(lons) or 0.001

    is_round_trip = (
        abs(end_lat - start_lat) / lat_span < ROUND_TRIP_THRESHOLD
        and abs(end_lon - start_lon) / lon_span < ROUND_TRIP_THRESHOLD
    )
    if is_round_trip:
        end_lat += lat_span * ROUND_TRIP_OFFSET
        end_lon += lon_span * ROUND_TRIP_OFFSET

    return [
        MapMarker(start_lat, start_lon, start_label, True),
        MapMarker(end_lat, end_lon, ziel_label, True),
    ]


def _render_subheader(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    y0 = HEADER_HEIGHT

    label_font = font(SUBHEADER_LABEL_SIZE)
    label_cap_top = label_font.getbbox("M")[1]
    draw_tracked(draw, (MARGIN_LEFT, y0 + 8 - label_cap_top), "LETZTE AKTIVITÄT",
                label_font, BLACK, SUBHEADER_LABEL_TRACKING)

    category = aggregator.categorize(activity)
    local_dt = _parse_local(activity["start_date_local"])
    date_text = f"{WEEKDAY_DE[local_dt.weekday()]} {local_dt:%d.%m.%Y}"

    date_font = font(DATE_LABEL_SIZE)
    date_w = tracked_width(draw, date_text, date_font, DATE_LABEL_TRACKING)
    badge_w, _ = badge_size(draw, category)

    badge_top = y0 + 20
    badge_x0 = WIDTH - MARGIN_RIGHT - date_w - 10 - badge_w
    badge_box = render_badge(draw, (badge_x0, badge_top), category)

    row_mid = (badge_box[1] + badge_box[3]) / 2
    draw_tracked(draw, (badge_box[2] + 10, row_mid), date_text, date_font, BLACK,
                DATE_LABEL_TRACKING, anchor="lm")

    name_font = font(ACTIVITY_NAME_SIZE, bold=True)
    full_name = _display_name(activity["name"])
    name = full_name
    max_width = badge_x0 - 10 - MARGIN_LEFT
    while draw.textlength(name, font=name_font) > max_width and len(name) > 10:
        name = name[:-1]
    if name != full_name:
        name = name.rstrip() + "…"
    draw.text((MARGIN_LEFT, y0 + 22), name, font=name_font, fill=BLACK)


def _render_map_column(draw: ImageDraw.ImageDraw, activity: dict, streams: dict | None) -> None:
    box = (MARGIN_LEFT, HEADER_HEIGHT + SUBHEADER_HEIGHT + 8,
           MAP_COLUMN_X1, SUBSTATS_Y0 - 6)

    poly = activity.get("map", {}).get("polyline") or activity.get("map", {}).get("summary_polyline")
    tracks = []
    
    if streams and "latlng" in streams and streams["latlng"].get("data"):
        points = streams["latlng"]["data"]
        pts = [(p[0], p[1]) for p in points]
        if pts:
            tracks.append(pts)
    elif poly:
        pts = pl.decode(poly)
        if pts:
            tracks.append(pts)

    markers = None
    if tracks:
        points = tracks[0]
        start_local = _parse_local(activity["start_date_local"])
        elapsed = activity.get("elapsed_time") or activity.get("moving_time", 0)
        ziel_local = start_local + timedelta(seconds=elapsed)
        markers = _prepare_markers(
            points,
            f"START {start_local:%H:%M}",
            f"ZIEL {ziel_local:%H:%M}",
        )

    render_map(draw, box, tracks, markers=markers)


def _render_main_stats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    y0 = HEADER_HEIGHT + SUBHEADER_HEIGHT + 8
    y1 = MAIN_CONTENT_Y1
    x0, x1 = STAT_COLUMN_X0, WIDTH - MARGIN_RIGHT

    stats = [
        ("DISTANZ", format_number(activity["distance"] / 1000, 1), "km"),
        ("HÖHE", format_number(activity.get("total_elevation_gain", 0)), "hm"),
        ("ZEIT", _format_duration_short(activity.get("moving_time", 0)), "h"),
        ("Ø SPEED", format_number(activity.get("average_speed", 0) * 3.6, 1), "km/h"),
    ]

    block_h = (y1 - y0) / STAT_ROW_COUNT
    gap = 10
    for i, (label, value, unit) in enumerate(stats):
        block_y0 = y0 + i * block_h
        block_y1 = block_y0 + block_h - gap
        render_stat_block(draw, (x0, block_y0, x1, block_y1), label, value, unit)
        if i > 0:
            draw.line([(x0, block_y0 - gap / 2), (x1, block_y0 - gap / 2)],
                      fill=BLACK, width=1)


def _render_substats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    x0, x1 = MARGIN_LEFT, MAP_COLUMN_X1
    y0, y1 = SUBSTATS_Y0, SUBSTATS_Y1

    avg_hr_value, avg_hr_unit = _hr_value(activity, "average_heartrate")
    max_hr_value, max_hr_unit = _hr_value(activity, "max_heartrate")
    cal_value, cal_unit = _calories_value(activity)
    kudos = activity.get("kudos_count", 0)

    # unit_size=None everywhere except KUDOS: the heart glyph needs a fixed
    # legible size - the normal value_size*UNIT_RATIO scaling shrinks it to
    # an illegible dot at this small value_size (26 * 0.30 = 8px).
    cols = [
        ("Ø PULS", avg_hr_value, avg_hr_unit, None),
        ("MAX PULS", max_hr_value, max_hr_unit, None),
        ("KALORIEN", cal_value, cal_unit, None),
        ("KUDOS", str(kudos), KUDOS_HEART, 16),
    ]
    col_w = (x1 - x0) / len(cols)
    for i, (label, value, unit, unit_size) in enumerate(cols):
        col_x0 = x0 + i * col_w
        col_x1 = col_x0 + col_w - SUB_STAT_COL_GAP
        render_stat_block(draw, (col_x0, y0, col_x1, y1), label, value, unit,
                          value_size=SUB_STAT_VALUE_SIZE, unit_size=unit_size)
        if i > 0:
            draw.line([(col_x0 - 5, y0), (col_x0 - 5, y1)], fill=BLACK, width=1)


def _render_elevation_section(draw: ImageDraw.ImageDraw, streams: dict | None) -> None:
    box = (MARGIN_LEFT, ELEVATION_Y0 + 10, WIDTH - MARGIN_RIGHT, HEIGHT - 6)

    altitude = (streams or {}).get("altitude", {}).get("data") or []
    distance = (streams or {}).get("distance", {}).get("data") or []
    heartrate = (streams or {}).get("heartrate", {}).get("data") or None

    if not altitude or not distance or len(altitude) < 2:
        title_font = font(9)
        cap_top = title_font.getbbox("M")[1]
        draw_tracked(draw, (box[0], box[1] - cap_top), "HÖHENPROFIL", title_font,
                    BLACK, 1.5)
        msg_font = font(12)
        draw.text(((box[0] + box[2]) / 2 - 60, (box[1] + box[3]) / 2 - 8),
                  "Keine Höhendaten", font=msg_font, fill=BLACK)
        return

    render_elevation(draw, box, altitude, distance, heartrate)


def render_dashboard(
    activity: dict,
    streams: dict | None = None,
    athlete_name: str = "",
    updated_at: datetime | None = None,
) -> Image.Image:
    """Single-activity detail view: map, stats, elevation profile.

    athlete_name defaults to "" for backward compatibility with the previous
    2-arg call signature; the header component requires *some* name, but
    every real caller (app.py) passes the athlete's actual name.
    """
    img = Image.new("1", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    year = _parse_local(activity["start_date_local"]).year
    render_header(draw, (0, 0, WIDTH, HEADER_HEIGHT), year, athlete_name, updated_at)

    _render_subheader(draw, activity)

    draw.line([(0, HEADER_HEIGHT + SUBHEADER_HEIGHT),
               (WIDTH, HEADER_HEIGHT + SUBHEADER_HEIGHT)], fill=BLACK, width=1)

    _render_map_column(draw, activity, streams)
    _render_main_stats(draw, activity)
    _render_substats(draw, activity)

    draw.line([(0, MAIN_CONTENT_Y1), (WIDTH, MAIN_CONTENT_Y1)], fill=BLACK, width=1)

    _render_elevation_section(draw, streams)

    return img


if __name__ == "__main__":
    import math

    def _fake_track(lat0, lon0, n=200, round_trip=False):
        pts = []
        for i in range(n):
            t = i / n
            forward = t if t < 0.5 or not round_trip else 1 - t
            pts.append((
                lat0 + 0.06 * forward + 0.01 * math.sin(t * 9 * math.pi),
                lon0 + 0.18 * forward + 0.01 * math.cos(t * 7 * math.pi),
            ))
        return pl.encode(pts)

    activity = {
        "name": "NOCKSPITZE FEIERABENDRUNDE",
        "sport_type": "MountainBikeRide",
        "type": "MountainBikeRide",
        "start_date": "2026-08-16T17:04:00Z",
        "start_date_local": "2026-08-16T17:04:00Z",
        "distance": 42100,
        "total_elevation_gain": 980,
        "moving_time": 2 * 3600 + 48 * 60,
        "elapsed_time": 2 * 3600 + 48 * 60 + 16 * 60,
        "average_speed": 42100 / (2 * 3600 + 48 * 60),
        "average_heartrate": 142,
        "max_heartrate": 178,
        "calories": 1980,
        "kudos_count": 42,
        "map": {"summary_polyline": _fake_track(47.22, 11.28)},
    }

    n = 300
    distance_stream = [i / (n - 1) * 42100 for i in range(n)]
    altitude_stream = [
        610 + 1330 * (0.5 - 0.5 * math.cos(i / n * 2.2 * math.pi)) ** 1.1
        for i in range(n)
    ]
    heartrate_stream = [128 + 40 * (0.5 - 0.5 * math.cos((i + 30) / n * 2.1 * math.pi))
                         for i in range(n)]
    streams = {
        "altitude": {"data": altitude_stream},
        "distance": {"data": distance_stream},
        "heartrate": {"data": heartrate_stream},
        "latlng": {"data": [[47.22 + 0.06 * (i/n) + 0.01 * math.sin((i/n)*9*math.pi), 11.28 + 0.18 * (i/n) + 0.01 * math.cos((i/n)*7*math.pi)] for i in range(n)]},
    }

    img = render_dashboard(activity, streams, "Malte Braig", datetime(2026, 8, 16, 19, 12))
    out = Path(__file__).resolve().parent / "preview_activity.png"
    img.save(out)
    print(f"wrote {out}")

    # No-HR / no-kudos / no-calories / round-trip / no-streams variant
    activity_minimal = dict(activity)
    activity_minimal["name"] = "Wanderung am Morgen"
    activity_minimal["average_heartrate"] = None
    activity_minimal["max_heartrate"] = None
    activity_minimal["calories"] = None
    activity_minimal["kudos_count"] = 0
    activity_minimal["map"] = {"summary_polyline": _fake_track(47.2, 11.3, round_trip=True)}

    img2 = render_dashboard(activity_minimal, None, "Malte Braig", datetime(2026, 8, 16, 19, 12))
    out2 = Path(__file__).resolve().parent / "preview_activity_minimal.png"
    img2.save(out2)
    print(f"wrote {out2}")
