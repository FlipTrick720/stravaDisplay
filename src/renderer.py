"""Render Strava activity to a 800x480 image for e-paper display.

Renders in 1-bit mode (black/white) - what the Waveshare 7.5" V2 supports.
Kept modular so we can swap layouts easily.
"""
from datetime import datetime
from pathlib import Path
from typing import Iterable
import polyline
from PIL import Image, ImageDraw, ImageFont

# Display size (Waveshare 7.5" V2)
WIDTH, HEIGHT = 800, 480

# Layout: left panel is the map, right panel is the stats
MAP_WIDTH = 500
STATS_X = MAP_WIDTH + 20
HEADER_HEIGHT = 60
FOOTER_HEIGHT = 60
MAP_MARGIN = 15

# Fonts: use bundled DejaVu (comes with python3-pil on Raspbian)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


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
    """Strava returns ISO8601 with Z. Format as '15.08.2026 · 12:34'."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y · %H:%M")


def _project_polyline(
    points: Iterable[tuple[float, float]],
    box: tuple[int, int, int, int],
) -> list[tuple[int, int]]:
    """Project (lat, lon) tuples to pixel coords inside box (x0, y0, x1, y1).

    Preserves aspect ratio, centers inside the box. Latitude increases north,
    so we flip Y (screen Y grows downward).
    """
    points = list(points)
    if not points:
        return []

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    lat_range = lat_max - lat_min or 1e-9
    lon_range = lon_max - lon_min or 1e-9

    x0, y0, x1, y1 = box
    box_w = x1 - x0
    box_h = y1 - y0

    # Use the smaller scale to preserve aspect ratio
    scale = min(box_w / lon_range, box_h / lat_range)

    # Center the drawing inside the box
    x_offset = x0 + (box_w - lon_range * scale) / 2
    y_offset = y0 + (box_h - lat_range * scale) / 2

    return [
        (
            int(x_offset + (lon - lon_min) * scale),
            int(y_offset + (lat_max - lat) * scale),  # Flip Y
        )
        for lat, lon in points
    ]


def _draw_track(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Draw activity polyline in the left panel."""
    poly = activity.get("map", {}).get("summary_polyline")
    box = (MAP_MARGIN, HEADER_HEIGHT + MAP_MARGIN,
           MAP_WIDTH - MAP_MARGIN, HEIGHT - FOOTER_HEIGHT - MAP_MARGIN)

    if not poly:
        # Placeholder if no GPS track
        draw.rectangle(box, outline=0, width=1)
        draw.text(
            ((box[0] + box[2]) // 2 - 60, (box[1] + box[3]) // 2 - 10),
            "no GPS track",
            font=_font(16),
            fill=0,
        )
        return

    points = polyline.decode(poly)
    pixels = _project_polyline(points, box)

    # Draw a thicker line by drawing multiple offset lines
    for offset in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        shifted = [(x + offset[0], y + offset[1]) for x, y in pixels]
        draw.line(shifted, fill=0, width=1)


def _draw_stats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Draw stats block on the right side."""
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


def _draw_header(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Title + date at top."""
    title = activity["name"][:45]  # Truncate long titles
    draw.text((MAP_MARGIN, 10), title, font=_font(22, bold=True), fill=0)
    draw.text((MAP_MARGIN, 36), _format_date(activity["start_date_local"]),
              font=_font(14), fill=0)
    draw.line([(0, HEADER_HEIGHT), (WIDTH, HEADER_HEIGHT)], fill=0, width=1)


def _draw_elevation_profile(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Placeholder for elevation profile at the bottom.

    Real elevation stream requires /activities/{id}/streams call - we'll add
    that later. For now, just show total elevation as text.
    """
    y_top = HEIGHT - FOOTER_HEIGHT
    draw.line([(0, y_top), (WIDTH, y_top)], fill=0, width=1)

    label = f"Höhenprofil: coming soon"
    draw.text((MAP_MARGIN, y_top + 20), label, font=_font(14), fill=0)


def render_dashboard(activity: dict) -> Image.Image:
    """Render a single activity as a dashboard image (800x480, 1-bit)."""
    img = Image.new("1", (WIDTH, HEIGHT), 1)  # 1 = white
    draw = ImageDraw.Draw(img)

    _draw_header(draw, activity)
    _draw_track(draw, activity)
    _draw_stats(draw, activity)
    _draw_elevation_profile(draw, activity)

    return img


if __name__ == "__main__":
    # Smoke test - fetch last activity via client, render to PNG
    import strava_client

    client = strava_client.StravaClient()
    activities = client.activities(per_page=1)
    if not activities:
        raise SystemExit("No activities found")

    # Summary list doesn't include polyline - need to fetch full activity
    activity = client.activity(activities[0]["id"])

    img = render_dashboard(activity)
    output_path = Path(__file__).parent.parent / "preview.png"
    img.save(output_path)
    print(f"Rendered preview to {output_path}")
    print(f"Activity: {activity['name']} ({activity['distance']/1000:.1f} km)")
