import re

# Patch overview.py
with open("views/overview.py", "r") as f:
    overview_src = f.read()

overview_src = overview_src.replace(
    "from components.map_view import render_map",
    "from components.map_view import render_map, decode_polylines"
)
overview_src = overview_src.replace(
    "render_map(draw, (x0, map_y0, x1, map_y1), stats.polylines)",
    "tracks = decode_polylines(stats.polylines)\n    render_map(draw, (x0, map_y0, x1, map_y1), tracks)"
)

with open("views/overview.py", "w") as f:
    f.write(overview_src)

# Patch activity.py
with open("views/activity.py", "r") as f:
    activity_src = f.read()

activity_src = activity_src.replace(
    "def _render_map_column(draw: ImageDraw.ImageDraw, activity: dict) -> None:",
    "def _render_map_column(draw: ImageDraw.ImageDraw, activity: dict, streams: dict | None) -> None:"
)
activity_src = activity_src.replace(
    "_render_map_column(draw, activity)",
    "_render_map_column(draw, activity, streams)"
)

old_map_column = """    poly = activity.get("map", {}).get("polyline") or activity.get("map", {}).get("summary_polyline")
    markers = None
    if poly:
        points = pl.decode(poly)
        if points:
            start_local = _parse_local(activity["start_date_local"])
            elapsed = activity.get("elapsed_time") or activity.get("moving_time", 0)
            ziel_local = start_local + timedelta(seconds=elapsed)
            markers = _prepare_markers(
                points,
                f"START {start_local:%H:%M}",
                f"ZIEL {ziel_local:%H:%M}",
            )

    render_map(draw, box, [poly] if poly else [], markers=markers)"""

new_map_column = """    poly = activity.get("map", {}).get("polyline") or activity.get("map", {}).get("summary_polyline")
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

    render_map(draw, box, tracks, markers=markers)"""

activity_src = activity_src.replace(old_map_column, new_map_column)

with open("views/activity.py", "w") as f:
    f.write(activity_src)

print("patched")
