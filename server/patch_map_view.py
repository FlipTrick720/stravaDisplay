import re

with open("components/map_view.py", "r") as f:
    content = f.read()

# 1. Add tile_client import
if "import tile_client" not in content:
    content = content.replace("import polyline as pl\nfrom PIL import ImageDraw", "import polyline as pl\nfrom PIL import ImageDraw, Image\nimport tile_client")

# 2. Modify draw_cities signature and body
content = re.sub(
    r"def draw_cities\(\n\s*draw: ImageDraw\.ImageDraw,\n\s*box: tuple\[int, int, int, int\],\n\s*bounds: tuple\[float, float, float, float\],\n\s*cities: list\[Tuple\[str, float, float\]\],\n\) -> None:",
    "def draw_cities(\n    draw: ImageDraw.ImageDraw,\n    box: tuple[int, int, int, int],\n    project_fn,\n    cities: list[Tuple[str, float, float]],\n) -> None:",
    content
)
content = content.replace("x, y = project_point(lat, lon, box, bounds)", "x, y = project_fn(lat, lon)")

# 3. Modify draw_markers signature and body
content = re.sub(
    r"def draw_markers\(\n\s*draw: ImageDraw\.ImageDraw,\n\s*box: tuple\[int, int, int, int\],\n\s*bounds: tuple\[float, float, float, float\],\n\s*markers: list\[MapMarker\],\n\) -> None:",
    "def draw_markers(\n    draw: ImageDraw.ImageDraw,\n    box: tuple[int, int, int, int],\n    project_fn,\n    markers: list[MapMarker],\n) -> None:",
    content
)
content = content.replace("x, y = project_point(marker.lat, marker.lon, box, bounds)", "x, y = project_fn(marker.lat, marker.lon)")

# 4. Rewrite render_map
# We need to replace the body of render_map. Let's find it.
render_map_def = """def render_map(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    polylines: list[str],
    cities_in_bounds: list[Tuple[str, float, float]] | None = None,
    markers: list[MapMarker] | None = None,
    border: bool = True,
    max_cities: int = 6,
    track_width: int = TRACK_WIDTH,
    pad_ratio: float = BOUNDS_PAD_RATIO,
) -> None:"""

new_render_map = """def render_map(
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
        
    draw_compass(draw, inner)"""

# We use regex to replace everything from `def render_map` to the end of the file.
content = re.sub(r"def render_map\(.*", new_render_map, content, flags=re.DOTALL)

with open("components/map_view.py", "w") as f:
    f.write(content)

print("patched")
