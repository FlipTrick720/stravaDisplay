"""Render Strava data to 800x480 images for the e-paper display."""
from datetime import datetime
from pathlib import Path
from typing import Iterable
from math import cos, radians
import polyline as pl
from PIL import Image, ImageDraw, ImageFont

import cities

WIDTH, HEIGHT = 800, 480

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
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def _format_duration(seconds: int) -> str:
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}:{m:02d} h"
    return f"{seconds // 60} min"


def _format_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y · %H:%M")


def _time_ago(iso: str) -> str:
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
    all_lats: list[float] = []
    all_lons: list[float] = []
    for poly in polylines:
        for lat, lon in pl.decode(poly):
            all_lats.append(lat)
            all_lons.append(lon)
    if not all_lats:
        return None
    return (min(all_lats), max(all_lats), min(all_lons), max(all_lons))


def _project_point(
    lat: float,
    lon: float,
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    """Project a single (lat, lon) into the box using the given bounds."""
    return _project_polyline([(lat, lon)], box, bounds)[0]


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Simple word-wrap on whitespace.

    Returns list of lines, each not exceeding max_chars (as long as individual
    words fit).
    """
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# =========================
# Map context: cities, compass, scale
# =========================

def _draw_cities(
    img: Image.Image,
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
    max_cities: int = 6,
) -> None:
    """Draw city labels within the given lat/lon bounds inside the box."""
    lat_min, lat_max, lon_min, lon_max = bounds
    in_bounds = cities.cities_in_bounds(lat_min, lat_max, lon_min, lon_max, max_cities)
    if not in_bounds:
        return

    draw = ImageDraw.Draw(img)
    font = _font(10)

    for name, lat, lon in in_bounds:
        x, y = _project_point(lat, lon, box, bounds)
        # Small filled circle for the city dot
        draw.ellipse([(x - 2, y - 2), (x + 2, y + 2)], fill=0)
        # Label to the right, slightly offset
        draw.text((x + 5, y - 6), name, font=font, fill=0)


def _draw_scale_bar(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
) -> None:
    """Draw a small scale bar in the bottom-left of the box.

    Shows a nice round number of km based on the current zoom level.
    """
    x0, y0, x1, y1 = box
    lat_min, lat_max, lon_min, lon_max = bounds

    # Compute km per pixel at the middle latitude
    mid_lat = (lat_min + lat_max) / 2
    box_w = x1 - x0
    lon_range = lon_max - lon_min or 1e-9
    km_per_deg_lon = 111.0 * cos(radians(mid_lat))
    km_per_pixel = (lon_range * km_per_deg_lon) / box_w

    # Pick a nice round number of km that fits in ~15-25% of panel width
    target_pixels = box_w * 0.2
    target_km = target_pixels * km_per_pixel

    # Snap to nice value: 1, 2, 5, 10, 20, 50, 100 km
    for nice in [1, 2, 5, 10, 20, 50, 100, 200]:
        if nice >= target_km:
            bar_km = nice
            break
    else:
        bar_km = 200

    bar_pixels = int(bar_km / km_per_pixel)

    # Position: bottom-left of box, small inset
    bar_x = x0 + 8
    bar_y = y1 - 10

    draw.line([(bar_x, bar_y), (bar_x + bar_pixels, bar_y)], fill=0, width=2)
    # Small ticks at ends
    draw.line([(bar_x, bar_y - 3), (bar_x, bar_y + 3)], fill=0, width=1)
    draw.line([(bar_x + bar_pixels, bar_y - 3), (bar_x + bar_pixels, bar_y + 3)], fill=0, width=1)
    draw.text((bar_x + bar_pixels + 4, bar_y - 8), f"{bar_km} km", font=_font(10), fill=0)


def _draw_compass(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
) -> None:
    """Small N-arrow in the top-right of the box."""
    x0, y0, x1, y1 = box
    cx = x1 - 15
    cy = y0 + 15
    # Arrow: up-pointing triangle
    draw.polygon([(cx, cy - 6), (cx - 4, cy + 4), (cx + 4, cy + 4)], fill=0)
    draw.text((cx - 4, cy + 5), "N", font=_font(9, bold=True), fill=0)


# =========================
# Layout A: latest activity
# =========================

def _draw_activity_header(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    title = activity["name"][:45]
    draw.text((MAP_MARGIN, 10), title, font=_font(22, bold=True), fill=0)
    draw.text((MAP_MARGIN, 36), _format_date(activity["start_date_local"]),
              font=_font(14), fill=0)
    draw.line([(0, HEADER_HEIGHT), (WIDTH, HEADER_HEIGHT)], fill=0, width=1)


def _draw_activity_track(img: Image.Image, activity: dict) -> None:
    """Draw single activity polyline in the left panel with map context."""
    draw = ImageDraw.Draw(img)
    poly = activity.get("map", {}).get("summary_polyline")
    box = (MAP_MARGIN, HEADER_HEIGHT + MAP_MARGIN,
           MAP_WIDTH - MAP_MARGIN, HEIGHT - FOOTER_HEIGHT - MAP_MARGIN)

    if not poly:
        draw.rectangle(box, outline=0, width=1)
        draw.text(
            ((box[0] + box[2]) // 2 - 60, (box[1] + box[3]) // 2 - 10),
            "no GPS track", font=_font(16), fill=0,
        )
        return

    points = pl.decode(poly)
    # Padded bounds so cities near track edges still show
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    pad_lat = (max(lats) - min(lats)) * 0.15 or 0.02
    pad_lon = (max(lons) - min(lons)) * 0.15 or 0.02
    bounds = (min(lats) - pad_lat, max(lats) + pad_lat,
              min(lons) - pad_lon, max(lons) + pad_lon)

    # Cities under the track
    _draw_cities(img, box, bounds, max_cities=4)

    # Track on top
    pixels = _project_polyline(points, box, bounds)
    for offset in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        shifted = [(x + offset[0], y + offset[1]) for x, y in pixels]
        draw.line(shifted, fill=0, width=1)

    # Map context overlays
    _draw_compass(draw, box)
    _draw_scale_bar(draw, box, bounds)


def _draw_activity_stats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
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
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_activity_header(draw, activity)
    _draw_activity_track(img, activity)
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
    text = f"{year}  ·  {athlete_name.upper()}"
    draw.text((MAP_MARGIN, 10), text, font=_font(22, bold=True), fill=0)
    draw.line([(0, HEADER_HEIGHT), (WIDTH, HEADER_HEIGHT)], fill=0, width=1)


def _draw_ski_grid(
    img: Image.Image,
    stats,
    tracks_box: tuple[int, int, int, int],
) -> None:
    """Render each ski tour as an individual small vignette in a grid.

    Grid is 2 or 3 columns depending on count. Each cell scales to fit that
    single track (better than a big cluttered overlay for sparse categories).
    """
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = tracks_box
    box_w = x1 - x0
    box_h = y1 - y0

    n = len(stats.polylines)
    if n == 0:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        draw.text((cx - 40, cy - 8), "no tracks", font=_font(14), fill=0)
        return

    # Grid dimensions
    cols = 3 if n > 4 else 2
    rows = (n + cols - 1) // cols

    cell_w = box_w // cols
    cell_h = box_h // rows
    pad = 4

    for i, poly in enumerate(stats.polylines):
        row = i // cols
        col = i % cols
        cell_box = (
            x0 + col * cell_w + pad,
            y0 + row * cell_h + pad,
            x0 + (col + 1) * cell_w - pad,
            y0 + (row + 1) * cell_h - pad,
        )

        points = pl.decode(poly)
        pixels = _project_polyline(points, cell_box)
        if len(pixels) >= 2:
            for offset in [(0, 0), (1, 0), (0, 1)]:
                shifted = [(x + offset[0], y + offset[1]) for x, y in pixels]
                draw.line(shifted, fill=0, width=1)


def _draw_category_panel(
    img: Image.Image,
    stats,
    box: tuple[int, int, int, int],
) -> None:
    """One category panel: label + overlaid tracks with map context + stats."""
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box

    # Category label
    draw.text((x0 + 12, y0 + 8), stats.category.upper(),
              font=_font(20, bold=True), fill=0)

    stats_h = 100
    tracks_box = (x0 + 8, y0 + 38, x1 - 8, y1 - stats_h)

    if stats.polylines:
        bounds = _compute_global_bounds(stats.polylines)
        lat_min, lat_max, lon_min, lon_max = bounds
        pad_lat = (lat_max - lat_min) * 0.08 or 0.02
        pad_lon = (lon_max - lon_min) * 0.08 or 0.02
        padded_bounds = (
            lat_min - pad_lat, lat_max + pad_lat,
            lon_min - pad_lon, lon_max + pad_lon,
        )

        _draw_cities(img, tracks_box, padded_bounds, max_cities=5)

        for poly in stats.polylines:
            points = pl.decode(poly)
            pixels = _project_polyline(points, tracks_box, padded_bounds)
            if len(pixels) >= 2:
                draw.line(pixels, fill=0, width=1)

        _draw_compass(draw, tracks_box)
        _draw_scale_bar(draw, tracks_box, padded_bounds)
    else:
        cx = (tracks_box[0] + tracks_box[2]) // 2
        cy = (tracks_box[1] + tracks_box[3]) // 2
        draw.text((cx - 40, cy - 8), "no tracks", font=_font(14), fill=0)

    # Separator
    sep_y = y1 - stats_h
    draw.line([(x0 + 12, sep_y), (x1 - 12, sep_y)], fill=0, width=1)

    # Stats
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
    y_top = HEIGHT - FOOTER_HEIGHT
    draw.line([(0, y_top), (WIDTH, y_top)], fill=0, width=1)

    ago = _time_ago(activity["start_date"])
    name = activity["name"][:40]
    dist = activity["distance"] / 1000
    text = f"Last: {name}  ·  {ago}  ·  {dist:.1f} km"
    draw.text((MAP_MARGIN, y_top + 20), text, font=_font(14), fill=0)


def render_overview(overview, athlete_name: str) -> Image.Image:
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_overview_header(draw, overview.year, athlete_name)

    panel_top = HEADER_HEIGHT
    panel_bottom = HEIGHT - FOOTER_HEIGHT
    mid_x = WIDTH // 2

    draw.line([(mid_x, panel_top), (mid_x, panel_bottom)], fill=0, width=1)

    if len(overview.categories) >= 1:
        _draw_category_panel(img, overview.categories[0],
                             (0, panel_top, mid_x, panel_bottom))
    if len(overview.categories) >= 2:
        _draw_category_panel(img, overview.categories[1],
                             (mid_x, panel_top, WIDTH, panel_bottom))

    _draw_last_ride_footer(draw, overview.last_activity)

    return img


# =========================
# Error screen (Windows XP homage)
# =========================

def render_error(
    error_message: str,
    technical_details: str | None = None,
    heading: str | None = None,
) -> Image.Image:
    """Render a Windows XP style error dialog for display failures.

    Fills the entire 800x480 area (no border, no interactive elements since
    the display isn't touch).

    heading: optional short line above the message (e.g. "Zu viel Watt registriert").
             If None, uses the classic "Strava Display hat ein Problem festgestellt".
    """
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    # Title bar
    title_h = 40
    draw.rectangle([0, 0, WIDTH, title_h], fill=0)
    draw.text((16, 12), "Strava Display", font=_font(18, bold=True), fill=1)

    # [X] Close button (decorative only)
    x_box_size = 28
    x_box_x = WIDTH - x_box_size - 8
    x_box_y = (title_h - x_box_size) // 2
    draw.rectangle(
        [x_box_x, x_box_y, x_box_x + x_box_size, x_box_y + x_box_size],
        outline=1, fill=1,
    )
    draw.line([(x_box_x + 7, x_box_y + 7),
               (x_box_x + x_box_size - 7, x_box_y + x_box_size - 7)], fill=0, width=2)
    draw.line([(x_box_x + x_box_size - 7, x_box_y + 7),
               (x_box_x + 7, x_box_y + x_box_size - 7)], fill=0, width=2)

    # Content area
    content_top = title_h + 40

    # Big [X] warning icon
    icon_x = 60
    icon_y = content_top
    icon_size = 90
    draw.ellipse(
        [icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
        outline=0, width=4,
    )
    inset = 22
    draw.line(
        [(icon_x + inset, icon_y + inset),
         (icon_x + icon_size - inset, icon_y + icon_size - inset)],
        fill=0, width=6,
    )
    draw.line(
        [(icon_x + icon_size - inset, icon_y + inset),
         (icon_x + inset, icon_y + icon_size - inset)],
        fill=0, width=6,
    )

    # Heading (right of icon)
    text_x = icon_x + icon_size + 40
    text_y = content_top

    if heading:
        # Custom heading (word-wrap in case it's long)
        heading_lines = _wrap_text(heading, max_chars=32)
        for i, line in enumerate(heading_lines[:2]):
            draw.text((text_x, text_y + i * 32),
                      line, font=_font(22, bold=True), fill=0)
        heading_end_y = text_y + len(heading_lines[:2]) * 32
    else:
        draw.text((text_x, text_y), "Strava Display hat ein Problem",
                  font=_font(22, bold=True), fill=0)
        draw.text((text_x, text_y + 32), "festgestellt und muss beendet werden.",
                  font=_font(22, bold=True), fill=0)
        heading_end_y = text_y + 64

    # Error message
    msg_y = heading_end_y + 30
    draw.text((text_x, msg_y), "Fehlermeldung:", font=_font(14), fill=0)
    wrapped = _wrap_text(error_message, max_chars=48)
    for i, line in enumerate(wrapped[:4]):
        draw.text((text_x, msg_y + 22 + i * 20), line, font=_font(14), fill=0)

    # Technical details (optional)
    if technical_details:
        tech_y = HEIGHT - 90
        draw.text((60, tech_y), "Technische Details:", font=_font(12), fill=0)
        tech_wrapped = _wrap_text(technical_details, max_chars=80)
        for i, line in enumerate(tech_wrapped[:2]):
            draw.text((60, tech_y + 16 + i * 14), line, font=_font(12), fill=0)

    # Status bar hint
    info_y = HEIGHT - 24
    draw.text((60, info_y), "Falls das Problem weiterhin besteht, wende dich bitte an "
              "deinen Systemadministrator (Malte).", font=_font(12), fill=0)

    return img


# =========================
# CLI
# =========================

if __name__ == "__main__":
    import sys
    import strava_client
    import aggregator

    mode = sys.argv[1] if len(sys.argv) > 1 else "overview"

    if mode == "error":
        import error_messages
        # Optional: category via 2nd arg
        category = sys.argv[2] if len(sys.argv) > 2 else "overload"
        heading, message = error_messages.get_error(category)
        img = render_error(
            error_message=message,
            heading=heading,
            technical_details=f"Category: {category} · sample technical detail here",
        )
        out = "preview_error.png"
    else:
        client = strava_client.StravaClient()
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
