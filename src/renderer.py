"""Render Strava data to 800x480 images for the e-paper display.

Two views:
- render_dashboard(activity, streams): single activity (Layout A)
- render_overview(overview, athlete_name): YTD overview per category (Layout B)

All rendering is 1-bit black/white (native for Waveshare 7.5" V2).
"""
from datetime import datetime
from pathlib import Path
from typing import Iterable
import polyline as pl
from PIL import Image, ImageDraw, ImageFont

# =========================
# Layout constants
# =========================

WIDTH, HEIGHT = 800, 480

# Latest-activity view
MAP_WIDTH = 500
STATS_X = MAP_WIDTH + 20

HEADER_HEIGHT = 60
FOOTER_HEIGHT = 60
MAP_MARGIN = 15

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


# =========================
# Shared helpers
# =========================

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a DejaVu font at given size."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def _format_duration(seconds: int) -> str:
    """Seconds -> '1:24 h' or '45 min'."""
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}:{m:02d} h"
    return f"{seconds // 60} min"


def _format_date(iso: str) -> str:
    """ISO8601 -> '15.08.2026 · 12:34'."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y · %H:%M")


def _time_ago(iso: str) -> str:
    """ISO8601 -> 'vor 2h' / 'vor 15 min' / 'vor 3d'."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    now = datetime.now(dt.tzinfo)
    delta = now - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"vor {int(delta.total_seconds() / 60)} min"
    if hours < 24:
        return f"vor {int(hours)}h"
    return f"vor {int(hours / 24)}d"


def _project_polyline(
    points: Iterable[tuple[float, float]],
    box: tuple[int, int, int, int],
    global_bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[int, int]]:
    """Project (lat, lon) points into pixel box (x0, y0, x1, y1).

    Preserves aspect ratio, centers inside the box. Screen Y grows downward,
    latitude grows northward -> flip Y.

    If global_bounds (lat_min, lat_max, lon_min, lon_max) is passed, use those
    bounds instead of computing from `points`. Useful to project many tracks
    into the SAME coordinate system so they overlap correctly.
    """
    points = list(points)
    if not points:
        return []

    if global_bounds:
        lat_min, lat_max, lon_min, lon_max = global_bounds
    else:
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)

    lat_range = lat_max - lat_min or 1e-9
    lon_range = lon_max - lon_min or 1e-9

    x0, y0, x1, y1 = box
    box_w = x1 - x0
    box_h = y1 - y0

    scale = min(box_w / lon_range, box_h / lat_range)
    x_offset = x0 + (box_w - lon_range * scale) / 2
    y_offset = y0 + (box_h - lat_range * scale) / 2

    return [
        (
            int(x_offset + (lon - lon_min) * scale),
            int(y_offset + (lat_max - lat) * scale),
        )
        for lat, lon in points
    ]


def _compute_global_bounds(polylines: list[str]) -> tuple[float, float, float, float] | None:
    """Compute lat/lon bounds spanning ALL provided polylines."""
    all_lats: list[float] = []
    all_lons: list[float] = []
    for poly in polylines:
        for lat, lon in pl.decode(poly):
            all_lats.append(lat)
            all_lons.append(lon)
    if not all_lats:
        return None
    return (min(all_lats), max(all_lats), min(all_lons), max(all_lons))


# =========================
# Layout A: latest activity
# =========================

def _draw_activity_header(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Title + date at top."""
    title = activity["name"][:45]
    draw.text((MAP_MARGIN, 10), title, font=_font(22, bold=True), fill=0)
    draw.text((MAP_MARGIN, 36), _format_date(activity["start_date_local"]),
              font=_font(14), fill=0)
    draw.line([(0, HEADER_HEIGHT), (WIDTH, HEADER_HEIGHT)], fill=0, width=1)


def _draw_activity_track(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Draw single activity polyline in the left panel."""
    poly = activity.get("map", {}).get("summary_polyline")
    box = (MAP_MARGIN, HEADER_HEIGHT + MAP_MARGIN,
           MAP_WIDTH - MAP_MARGIN, HEIGHT - FOOTER_HEIGHT - MAP_MARGIN)

    if not poly:
        draw.rectangle(box, outline=0, width=1)
        draw.text(
            ((box[0] + box[2]) // 2 - 60, (box[1] + box[3]) // 2 - 10),
            "no GPS track",
            font=_font(16),
            fill=0,
        )
        return

    points = pl.decode(poly)
    pixels = _project_polyline(points, box)

    # Slightly thicker line via multi-pass offset
    for offset in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        shifted = [(x + offset[0], y + offset[1]) for x, y in pixels]
        draw.line(shifted, fill=0, width=1)


def _draw_activity_stats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Stats block on the right side."""
    stats = [
        ("DISTANZ", f"{activity['distance'] / 1000:.1f} km"),
        ("HÖHE", f"{int(activity.get('total_elevation_gain', 0))} hm"),
        ("ZEIT", _format_duration(int(activity.get('moving_time', 0)))),
        ("Ø SPEED", f"{activity.get('average_speed', 0) * 3.6:.1f} km/h"),
    ]
    y = HEADER_HEIGHT + 30
    for label, value in stats:
        draw.text((STATS_X, y), label, font=_font(14), fill=0)
        draw.text((STATS_X, y + 18), value, font=_font(32, bold=True), fill=0)
        y += 80


def _draw_elevation_profile(
    draw: ImageDraw.ImageDraw,
    streams: dict | None,
    activity: dict,
) -> None:
    """Elevation profile at the bottom (uses altitude+distance streams)."""
    y_top = HEIGHT - FOOTER_HEIGHT
    draw.line([(0, y_top), (WIDTH, y_top)], fill=0, width=1)

    if not streams or "altitude" not in streams or "distance" not in streams:
        draw.text((MAP_MARGIN, y_top + 20), "Höhenprofil: n/a", font=_font(14), fill=0)
        return

    altitudes = streams["altitude"]["data"]
    distances = streams["distance"]["data"]

    if len(altitudes) < 2:
        return

    plot_x0 = MAP_MARGIN
    plot_x1 = WIDTH - MAP_MARGIN
    plot_y0 = y_top + 12
    plot_y1 = HEIGHT - 6
    plot_w = plot_x1 - plot_x0
    plot_h = plot_y1 - plot_y0

    alt_min = min(altitudes)
    alt_max = max(altitudes)
    alt_range = alt_max - alt_min or 1.0
    dist_max = distances[-1] or 1.0

    # Subsample: one point per pixel column
    points = []
    for x in range(plot_w):
        target_dist = (x / plot_w) * dist_max
        idx = min(range(len(distances)), key=lambda i: abs(distances[i] - target_dist))
        alt = altitudes[idx]
        y = plot_y1 - int((alt - alt_min) / alt_range * plot_h)
        points.append((plot_x0 + x, y))

    polygon = points + [(plot_x1, plot_y1), (plot_x0, plot_y1)]
    draw.polygon(polygon, fill=0)

    draw.text((plot_x1 - 55, plot_y0 - 2), f"{int(alt_max)}m", font=_font(11), fill=0)
    draw.text((plot_x1 - 55, plot_y1 - 14), f"{int(alt_min)}m", font=_font(11), fill=0)


def render_dashboard(activity: dict, streams: dict | None = None) -> Image.Image:
    """Layout A: single activity dashboard."""
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_activity_header(draw, activity)
    _draw_activity_track(draw, activity)
    _draw_activity_stats(draw, activity)
    _draw_elevation_profile(draw, streams, activity)

    return img


# =========================
# Layout B: overview
# =========================

def _draw_overview_header(
    draw: ImageDraw.ImageDraw,
    year: int,
    athlete_name: str,
) -> None:
    """Top bar: year + athlete name."""
    text = f"{year}  ·  {athlete_name.upper()}"
    draw.text((MAP_MARGIN, 10), text, font=_font(22, bold=True), fill=0)
    draw.line([(0, HEADER_HEIGHT), (WIDTH, HEADER_HEIGHT)], fill=0, width=1)


def _draw_category_panel(
    draw: ImageDraw.ImageDraw,
    stats,  # aggregator.CategoryStats
    box: tuple[int, int, int, int],
) -> None:
    """One category panel: label + all tracks overlaid + stats."""
    x0, y0, x1, y1 = box

    # Category label
    draw.text((x0 + 12, y0 + 8), stats.category.upper(),
              font=_font(20, bold=True), fill=0)

    # Tracks area (below header, above stats)
    stats_h = 100
    tracks_box = (x0 + 8, y0 + 38, x1 - 8, y1 - stats_h)

    if stats.polylines:
        bounds = _compute_global_bounds(stats.polylines)
        for poly in stats.polylines:
            points = pl.decode(poly)
            pixels = _project_polyline(points, tracks_box, bounds)
            if len(pixels) >= 2:
                draw.line(pixels, fill=0, width=1)
    else:
        cx = (tracks_box[0] + tracks_box[2]) // 2
        cy = (tracks_box[1] + tracks_box[3]) // 2
        draw.text((cx - 40, cy - 8), "no tracks", font=_font(14), fill=0)

    # Separator line above stats block
    sep_y = y1 - stats_h
    draw.line([(x0 + 12, sep_y), (x1 - 12, sep_y)], fill=0, width=1)

    # Stats rows
    stat_lines = [
        f"{stats.count} rides",
        f"{stats.distance_m / 1000:.0f} km",
        f"{int(stats.elevation_m):,} hm".replace(",", "."),
        f"{stats.moving_time_s / 3600:.0f} h",
    ]
    row_y = sep_y + 10
    for line in stat_lines:
        draw.text((x0 + 12, row_y), line, font=_font(18, bold=True), fill=0)
        row_y += 22


def _draw_last_ride_footer(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Bottom bar: last ride summary."""
    y_top = HEIGHT - FOOTER_HEIGHT
    draw.line([(0, y_top), (WIDTH, y_top)], fill=0, width=1)

    ago = _time_ago(activity["start_date"])
    name = activity["name"][:40]
    dist = activity["distance"] / 1000
    text = f"Last: {name}  ·  {ago}  ·  {dist:.1f} km"

    draw.text((MAP_MARGIN, y_top + 20), text, font=_font(14), fill=0)


def render_overview(overview, athlete_name: str) -> Image.Image:
    """Layout B: 2 category panels side by side + overview header/footer."""
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_overview_header(draw, overview.year, athlete_name)

    panel_top = HEADER_HEIGHT
    panel_bottom = HEIGHT - FOOTER_HEIGHT
    mid_x = WIDTH // 2

    # Vertical divider between panels
    draw.line([(mid_x, panel_top), (mid_x, panel_bottom)], fill=0, width=1)

    if len(overview.categories) >= 1:
        _draw_category_panel(draw, overview.categories[0],
                             (0, panel_top, mid_x, panel_bottom))
    if len(overview.categories) >= 2:
        _draw_category_panel(draw, overview.categories[1],
                             (mid_x, panel_top, WIDTH, panel_bottom))

    _draw_last_ride_footer(draw, overview.last_activity)

    return img


# =========================
# CLI (smoke test)
# =========================

if __name__ == "__main__":
    import sys
    import strava_client
    import aggregator

    client = strava_client.StravaClient()
    mode = sys.argv[1] if len(sys.argv) > 1 else "overview"

    if mode == "latest":
        activities = client.activities(per_page=1)
        if not activities:
            raise SystemExit("No activities found")
        activity_id = activities[0]["id"]
        activity = client.activity(activity_id)
        streams = client.activity_streams(activity_id)
        img = render_dashboard(activity, streams)
        out = "preview_latest.png"
    else:
        year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
        activities = client.activities_since(year_start, per_page=100)
        overview = aggregator.build_overview(activities)
        athlete = client.athlete()
        name = f"{athlete['firstname']} {athlete['lastname']}"
        img = render_overview(overview, name)
        out = "preview_overview.png"

    output_path = Path(__file__).parent.parent / out
    img.save(output_path)
    print(f"Rendered {mode} to {output_path}")
