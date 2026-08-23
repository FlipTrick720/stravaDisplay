"""Year overview view: 2 category panels + last-activity footer.

Moved verbatim out of renderer.py (Phase 2 Step 2) - see activity.py's
module docstring for why this still reaches into renderer.* for shared
helpers and layout constants instead of the components/ package.
"""
import polyline as pl
from PIL import Image, ImageDraw

import renderer

# =========================
# Layout B: overview
# =========================

def _draw_overview_header(
    draw: ImageDraw.ImageDraw,
    year: int,
    athlete_name: str,
) -> None:
    text = f"{year}  ·  {athlete_name.upper()}"
    draw.text((renderer.MAP_MARGIN, 10), text, font=renderer._font(22, bold=True), fill=0)
    draw.line([(0, renderer.HEADER_HEIGHT), (renderer.WIDTH, renderer.HEADER_HEIGHT)], fill=0, width=1)


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
        draw.text((cx - 40, cy - 8), "no tracks", font=renderer._font(14), fill=0)
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
        pixels = renderer._project_polyline(points, cell_box)
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
              font=renderer._font(20, bold=True), fill=0)

    stats_h = 100
    tracks_box = (x0 + 8, y0 + 38, x1 - 8, y1 - stats_h)

    if stats.polylines:
        bounds = renderer._compute_global_bounds(stats.polylines)
        lat_min, lat_max, lon_min, lon_max = bounds
        pad_lat = (lat_max - lat_min) * 0.08 or 0.02
        pad_lon = (lon_max - lon_min) * 0.08 or 0.02
        padded_bounds = (
            lat_min - pad_lat, lat_max + pad_lat,
            lon_min - pad_lon, lon_max + pad_lon,
        )

        renderer._draw_cities(img, tracks_box, padded_bounds, max_cities=5)

        for poly in stats.polylines:
            points = pl.decode(poly)
            pixels = renderer._project_polyline(points, tracks_box, padded_bounds)
            if len(pixels) >= 2:
                draw.line(pixels, fill=0, width=1)

        renderer._draw_compass(draw, tracks_box)
        renderer._draw_scale_bar(draw, tracks_box, padded_bounds)
    else:
        cx = (tracks_box[0] + tracks_box[2]) // 2
        cy = (tracks_box[1] + tracks_box[3]) // 2
        draw.text((cx - 40, cy - 8), "no tracks", font=renderer._font(14), fill=0)

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
        draw.text((x0 + 12, row_y), line, font=renderer._font(18, bold=True), fill=0)
        row_y += 22


def _draw_last_ride_footer(draw: ImageDraw.ImageDraw, activity: dict) -> None:
    y_top = renderer.HEIGHT - renderer.FOOTER_HEIGHT
    draw.line([(0, y_top), (renderer.WIDTH, y_top)], fill=0, width=1)

    ago = renderer._time_ago(activity["start_date"])
    name = activity["name"][:40]
    dist = activity["distance"] / 1000
    text = f"Last: {name}  ·  {ago}  ·  {dist:.1f} km"
    draw.text((renderer.MAP_MARGIN, y_top + 20), text, font=renderer._font(14), fill=0)


def render_overview(overview, athlete_name: str) -> Image.Image:
    img = Image.new("1", (renderer.WIDTH, renderer.HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    _draw_overview_header(draw, overview.year, athlete_name)

    panel_top = renderer.HEADER_HEIGHT
    panel_bottom = renderer.HEIGHT - renderer.FOOTER_HEIGHT
    mid_x = renderer.WIDTH // 2

    draw.line([(mid_x, panel_top), (mid_x, panel_bottom)], fill=0, width=1)

    if len(overview.categories) >= 1:
        _draw_category_panel(img, overview.categories[0],
                             (0, panel_top, mid_x, panel_bottom))
    if len(overview.categories) >= 2:
        _draw_category_panel(img, overview.categories[1],
                             (mid_x, panel_top, renderer.WIDTH, panel_bottom))

    _draw_last_ride_footer(draw, overview.last_activity)

    return img

