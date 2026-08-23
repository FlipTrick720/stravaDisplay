"""Activity detail view: single-track map + stats + elevation profile.

Moved verbatim out of renderer.py (Phase 2 Step 2) - the shared drawing
helpers (_font, _project_polyline, _draw_cities, ...) and the WIDTH/HEIGHT
layout constants still live in renderer.py and are used here as
`renderer.<name>`. This is a straight move, not a refactor: Step 3 rebuilds
this view on top of the components/ package and drops the renderer.*
indirection then.
"""
import polyline as pl
from PIL import Image, ImageDraw

import renderer

# =========================
# Layout A: latest activity
# =========================

def _draw_activity_header(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    title = activity["name"][:45]
    draw.text((renderer.MAP_MARGIN, 10), title, font=renderer._font(22, bold=True), fill=0)
    draw.text((renderer.MAP_MARGIN, 36), renderer._format_date(activity["start_date_local"]),
              font=renderer._font(14), fill=0)
    draw.line([(0, renderer.HEADER_HEIGHT), (renderer.WIDTH, renderer.HEADER_HEIGHT)], fill=0, width=1)


def _draw_kudos_badge(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    """Draw kudos count as a badge in the top-right of the header area."""
    kudos = activity.get("kudos_count", 0)
    if kudos == 0:
        return  # no badge if no kudos

    text = f"{kudos}"
    label = "KUDOS"

    # Position: top-right, inside header area
    x_right = renderer.WIDTH - renderer.MAP_MARGIN
    y_top = 8

    # Draw label small above the number
    label_font = renderer._font(11, bold=True)
    number_font = renderer._font(28, bold=True)

    # Measure label so we can right-align
    label_bbox = draw.textbbox((0, 0), label, font=label_font)
    label_w = label_bbox[2] - label_bbox[0]
    number_bbox = draw.textbbox((0, 0), text, font=number_font)
    number_w = number_bbox[2] - number_bbox[0]

    # Heart symbol (small triangle-ish shape done with polygon)
    # We use ♥ from font, DejaVu supports it
    heart = "♥"
    heart_font = renderer._font(20)
    heart_bbox = draw.textbbox((0, 0), heart, font=heart_font)
    heart_w = heart_bbox[2] - heart_bbox[0]

    # Layout: KUDOS
    #         ♥ 42
    # Right-aligned
    total_w = number_w + heart_w + 4
    x_number = x_right - total_w
    x_heart = x_number + number_w + 4

    # Label above (centered above the number+heart cluster)
    x_label = x_right - label_w - 2
    draw.text((x_label, y_top), label, font=label_font, fill=0)

    # Number + heart on same baseline below label
    draw.text((x_number, y_top + 14), text, font=number_font, fill=0)
    draw.text((x_heart, y_top + 18), heart, font=heart_font, fill=0)


def _draw_activity_track(img: Image.Image, activity: dict) -> None:
    """Draw single activity polyline in the left panel with map context."""
    draw = ImageDraw.Draw(img)
    poly = activity.get("map", {}).get("summary_polyline")
    box = (renderer.MAP_MARGIN, renderer.HEADER_HEIGHT + renderer.MAP_MARGIN,
           renderer.MAP_WIDTH - renderer.MAP_MARGIN, renderer.HEIGHT - renderer.FOOTER_HEIGHT - renderer.MAP_MARGIN)

    if not poly:
        draw.rectangle(box, outline=0, width=1)
        draw.text(
            ((box[0] + box[2]) // 2 - 60, (box[1] + box[3]) // 2 - 10),
            "no GPS track", font=renderer._font(16), fill=0,
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
    renderer._draw_cities(img, box, bounds, max_cities=4)

    # Track on top
    pixels = renderer._project_polyline(points, box, bounds)
    for offset in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        shifted = [(x + offset[0], y + offset[1]) for x, y in pixels]
        draw.line(shifted, fill=0, width=1)

    # Map context overlays
    renderer._draw_compass(draw, box)
    renderer._draw_scale_bar(draw, box, bounds)


def _draw_activity_stats(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    stats = [
        ("DISTANZ", f"{activity['distance'] / 1000:.1f} km"),
        ("HÖHE", f"{int(activity.get('total_elevation_gain', 0))} hm"),
        ("ZEIT", renderer._format_duration(int(activity.get('moving_time', 0)))),
        ("Ø SPEED", f"{activity.get('average_speed', 0) * 3.6:.1f} km/h"),
    ]
    y = renderer.HEADER_HEIGHT + 30
    for label, value in stats:
        draw.text((renderer.STATS_X, y), label, font=renderer._font(14), fill=0)
        draw.text((renderer.STATS_X, y + 18), value, font=renderer._font(32, bold=True), fill=0)
        y += 80


def _draw_elevation_profile(
    draw: ImageDraw.ImageDraw,
    streams: dict | None,
    activity: dict,
) -> None:
    y_top = renderer.HEIGHT - renderer.FOOTER_HEIGHT
    draw.line([(0, y_top), (renderer.WIDTH, y_top)], fill=0, width=1)

    if not streams or "altitude" not in streams or "distance" not in streams:
        draw.text((renderer.MAP_MARGIN, y_top + 20), "Höhenprofil: n/a", font=renderer._font(14), fill=0)
        return

    altitudes = streams["altitude"]["data"]
    distances = streams["distance"]["data"]
    if len(altitudes) < 2:
        return

    plot_x0 = renderer.MAP_MARGIN
    plot_x1 = renderer.WIDTH - renderer.MAP_MARGIN
    plot_y0 = y_top + 12
    plot_y1 = renderer.HEIGHT - 6
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

    draw.text((plot_x1 - 55, plot_y0 - 2), f"{int(alt_max)}m", font=renderer._font(11), fill=0)
    draw.text((plot_x1 - 55, plot_y1 - 14), f"{int(alt_min)}m", font=renderer._font(11), fill=0)


def render_dashboard(activity: dict, streams: dict | None = None) -> Image.Image:
    img = Image.new("1", (renderer.WIDTH, renderer.HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_activity_header(draw, activity)
    _draw_kudos_badge(draw, activity)
    _draw_activity_track(img, activity)
    _draw_activity_stats(draw, activity)
    _draw_elevation_profile(draw, streams, activity)

    return img

