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
    from views import render_dashboard, render_overview

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
