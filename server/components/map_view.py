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
from PIL import ImageDraw

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


# =========================
# Projection
# =========================

def project_polyline(
    points: Iterable[tuple[float, float]],
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[int, int]]:
    """Project (lat, lon) pairs into pixel space, aspect-preserving and centred."""
    points = list(points)
    if not points:
        return []

    if bounds:
        lat_min, lat_max, lon_min, lon_max = bounds
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


def project_point(
    lat: float,
    lon: float,
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    return project_polyline([(lat, lon)], box, bounds)[0]


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
    bounds: tuple[float, float, float, float],
    cities: list[Tuple[str, float, float]],
) -> None:
    """Filled square plus a tracked uppercase label, as in the mocks."""
    fnt = font(CITY_LABEL_SIZE)
    cap_top = fnt.getbbox("M")[1]
    cap_h = fnt.getbbox("M")[3] - cap_top
    for name, lat, lon in cities:
        x, y = project_point(lat, lon, box, bounds)
        draw.rectangle([x - CITY_DOT, y - CITY_DOT, x + CITY_DOT, y + CITY_DOT],
                       fill=BLACK)
        draw_tracked(draw, (x + CITY_DOT + 4, y - cap_h / 2 - cap_top),
                     name.upper(), fnt, BLACK, CITY_LABEL_TRACKING)


def draw_markers(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
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
        x, y = project_point(marker.lat, marker.lon, box, bounds)
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
    """Draw tracks and map furniture into `box`.

    polylines are Strava encoded summary polylines. cities_in_bounds is the
    pre-filtered (name, lat, lon) list; pass None to look it up from cities.py
    against the computed bounds.
    """
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
        draw_tracked(draw, ((x0 + x1) / 2 - 45, (y0 + y1) / 2 - 6),
                     "KEIN GPS TRACK", fnt, BLACK, 1.0)
        return

    if cities_in_bounds is None:
        cities_in_bounds = _lookup_cities(*bounds, max_cities=max_cities)

    draw_cities(draw, inner, bounds, cities_in_bounds)

    for track in tracks:
        pixels = project_polyline(track, inner, bounds)
        if len(pixels) >= 2:
            draw.line(pixels, fill=BLACK, width=track_width, joint="curve")

    if markers:
        draw_markers(draw, inner, bounds, markers)

    draw_compass(draw, inner)


if __name__ == "__main__":
    import math
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from components.base import demo_canvas, save_preview

    def fake_track(lat0, lon0, turns, scale, n=260):
        pts = []
        for i in range(n):
            t = i / n * turns * 2 * math.pi
            pts.append((lat0 + scale * 0.5 * math.sin(t) + scale * 0.02 * i / n,
                        lon0 + scale * 1.6 * (i / n) + scale * 0.3 * math.cos(t * 1.7)))
        return pl.encode(pts)

    # Roughly the Innsbruck bowl, so real cities land inside the bounds.
    single = fake_track(47.22, 11.28, 1.5, 0.06)
    many = [fake_track(47.18 + i * 0.03, 11.15 + i * 0.05, 2 + i, 0.05)
            for i in range(5)]

    img, d = demo_canvas(800, 250)

    start_end = [
        MapMarker(47.2205, 11.2805, "START 17:04", True),
        MapMarker(47.2175, 11.2830, "ZIEL 19:52", True),
    ]
    render_map(d, (10, 10, 480, 240), [single], markers=start_end)

    render_map(d, (492, 10, 790, 240), many, max_cities=4)

    save_preview(img, "preview_map_view.png")
