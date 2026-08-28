"""Track map: projected polylines, city labels, compass, markers.

No tiles. The panel is 1-bit, so raster basemaps turn to mud; context comes
from the static city list plus a compass instead.

Projection and bounds are ported from renderer.py (_project_polyline /
_compute_global_bounds / _draw_compass) so the two produce identical
geometry while both exist.
"""
from __future__ import annotations

from typing import Iterable, NamedTuple, Tuple

import polyline as pl
from PIL import ImageDraw, Image
import tile_client

try:
    from components.base import BLACK, WHITE, draw_tracked, font, tracked_width
except ImportError:  # running this file directly
    from base import BLACK, WHITE, draw_tracked, font, tracked_width

# cities.py stays put in server/ because renderer.py still imports it. Resolve
# it whether we are imported as components.map_view (cwd server/, cities is a
# top-level module) or run directly as a file (server/ not on sys.path yet).
try:
    from cities import cities_in_bounds as _lookup_cities
except ImportError:  # pragma: no cover - direct execution
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cities import cities_in_bounds as _lookup_cities


class MapMarker(NamedTuple):
    lat: float
    lon: float
    label: str
    is_start_end: bool = False


CITY_LABEL_SIZE = 9
CITY_LABEL_TRACKING = 1.0
CITY_DOT = 2                 # half-size of the filled square

MARKER_LABEL_SIZE = 9
MARKER_LABEL_TRACKING = 1.0
MARKER_RADIUS = 5

TRACK_WIDTH = 2
BOUNDS_PAD_RATIO = 0.15
COMPASS_SIZE = 9





def compute_bounds(
    coords: list[tuple[float, float]],
    pad_ratio: float = BOUNDS_PAD_RATIO,
) -> tuple[float, float, float, float] | None:
    """(lat_min, lat_max, lon_min, lon_max) with padding so edge labels fit."""
    if not coords:
        return None
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    pad_lat = (max(lats) - min(lats)) * pad_ratio or 0.02
    pad_lon = (max(lons) - min(lons)) * pad_ratio or 0.02
    return (min(lats) - pad_lat, max(lats) + pad_lat,
            min(lons) - pad_lon, max(lons) + pad_lon)


def decode_polylines(polylines: list[str]) -> list[list[tuple[float, float]]]:
    tracks = []
    for poly in polylines:
        if not poly:
            continue
        points = pl.decode(poly)
        if points:
            tracks.append(points)
    return tracks


# =========================
# Overlays
# =========================

def draw_compass(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """North arrow in the top-right of the box."""
    _, y0, x1, _ = box
    cx = x1 - 15
    cy = y0 + 14
    draw.polygon([(cx, cy - 6), (cx - 4, cy + 4), (cx + 4, cy + 4)], fill=BLACK)
    draw.text((cx, cy + 6), "N", font=font(COMPASS_SIZE, bold=True), fill=BLACK,
              anchor="ma")


def draw_cities(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    project_fn,
    cities: list[Tuple[str, float, float]],
) -> None:
    """Filled square plus a tracked uppercase label, as in the mocks."""
    fnt = font(CITY_LABEL_SIZE)
    cap_top = fnt.getbbox("M")[1]
    cap_h = fnt.getbbox("M")[3] - cap_top
    for name, lat, lon in cities:
        x, y = project_fn(lat, lon)
        draw.rectangle([x - CITY_DOT, y - CITY_DOT, x + CITY_DOT, y + CITY_DOT],
                       fill=BLACK)
        
        text = name.upper()
        tw = tracked_width(draw, text, fnt, CITY_LABEL_TRACKING)
        label_x = x + CITY_DOT + 4
        if label_x + tw > box[2]:
            label_x = x - CITY_DOT - 4 - tw
            
        draw_tracked(draw, (label_x, y - cap_h / 2 - cap_top),
                     text, fnt, BLACK, CITY_LABEL_TRACKING)


def draw_markers(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    project_fn,
    markers: list[MapMarker],
) -> None:
    """START/ZIEL style markers.

    is_start_end=True gets the emphasized pair of glyphs from the mock: the
    first such marker is a filled disc (start), every later one a hollow square
    (finish). is_start_end=False is a plain small waypoint square.
    """
    fnt = font(MARKER_LABEL_SIZE)
    cap_top = fnt.getbbox("M")[1]
    cap_h = fnt.getbbox("M")[3] - cap_top
    seen_start = False
    placed: list[tuple[float, float, float, float]] = []

    for marker in markers:
        x, y = project_fn(marker.lat, marker.lon)
        if marker.is_start_end and not seen_start:
            draw.ellipse([x - MARKER_RADIUS, y - MARKER_RADIUS,
                          x + MARKER_RADIUS, y + MARKER_RADIUS], fill=BLACK)
            seen_start = True
        elif marker.is_start_end:
            r = MARKER_RADIUS - 1
            draw.rectangle([x - r, y - r, x + r, y + r],
                           fill=WHITE, outline=BLACK, width=2)
        else:
            draw.rectangle([x - 2, y - 2, x + 2, y + 2], fill=BLACK)

        if not marker.label:
            continue

        text = marker.label.upper()
        label_x = x + MARKER_RADIUS + 4
        label_y = y - cap_h / 2
        width = tracked_width(draw, text, fnt, MARKER_LABEL_TRACKING)
        # START and ZIEL usually sit within a few metres of each other; stack
        # their labels instead of overprinting, as the mock does.
        for _ in range(len(placed) + 1):
            rect = (label_x, label_y, label_x + width, label_y + cap_h)
            if not any(_overlaps(rect, other) for other in placed):
                break
            label_y += cap_h + 4
        placed.append((label_x, label_y, label_x + width, label_y + cap_h))
        draw_tracked(draw, (label_x, label_y - cap_top), text, fnt, BLACK,
                     MARKER_LABEL_TRACKING)


def _overlaps(a: tuple[float, float, float, float],
              b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


# =========================
# Component
# =========================

def render_map(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    polylines: list[str],
    cities_in_bounds: list[Tuple[str, float, float]] | None = None,
    markers: list[MapMarker] | None = None,
    border: bool = True,
    max_cities: int = 6,
    track_width: int = TRACK_WIDTH,
    pad_ratio: float = BOUNDS_PAD_RATIO,
) -> None:
    x0, y0, x1, y1 = box
    if border:
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=BLACK, width=1)

    inner = (x0 + 6, y0 + 6, x1 - 7, y1 - 7)
    tracks = decode_polylines(polylines)

    coords = [p for track in tracks for p in track]
    if markers:
        coords += [(m.lat, m.lon) for m in markers]
    bounds = compute_bounds(coords, pad_ratio)

    if bounds is None:
        fnt = font(11)
        tw = tracked_width(draw, "KEINE DATEN", fnt, 1.5)
        cap_top = fnt.getbbox("M")[1]
        cap_h = fnt.getbbox("M")[3] - cap_top
        cx = inner[0] + (inner[2] - inner[0]) / 2
        cy = inner[1] + (inner[3] - inner[1]) / 2
        draw_tracked(draw, (cx - tw / 2, cy - cap_h / 2 - cap_top),
                     "KEINE DATEN", fnt, BLACK, 1.5)
        return

    lat_min, lat_max, lon_min, lon_max = bounds
    box_w = inner[2] - inner[0]
    box_h = inner[3] - inner[1]

    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    
    zoom = tile_client.calculate_zoom(lat_min, lat_max, lon_min, lon_max, box_w, box_h)
    bg_img, projector = tile_client.get_centered_map_image(center_lat, center_lon, zoom, box_w, box_h)
    bg_1bit = bg_img.convert("1", dither=Image.FLOYDSTEINBERG)
    draw._image.paste(bg_1bit, (inner[0], inner[1]))

    def proj(lat, lon):
        px, py = projector(lat, lon)
        return (px + inner[0], py + inner[1])

    outline_width = track_width + 4
    for track in tracks:
        pts = [proj(lat, lon) for lat, lon in track]
        if len(pts) > 1:
            draw.line(pts, fill=WHITE, width=outline_width, joint="curve")

    for track in tracks:
        pts = [proj(lat, lon) for lat, lon in track]
        if len(pts) > 1:
            draw.line(pts, fill=BLACK, width=track_width, joint="curve")

    if markers:
        draw_markers(draw, inner, proj, markers)
        
    if cities_in_bounds is None:
        cities_in_bounds = _lookup_cities(lat_min, lat_max, lon_min, lon_max, max_cities)
    if cities_in_bounds:
        draw_cities(draw, inner, proj, cities_in_bounds)
        
    draw_compass(draw, inner)