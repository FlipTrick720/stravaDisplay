import re

with open("components/map_view.py", "r") as f:
    src = f.read()

smoothing_code = """def smooth_track(points: list[tuple[float, float]], iterations: int = 2) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    
    for _ in range(iterations):
        new_points = []
        new_points.append(points[0])
        for i in range(len(points) - 1):
            p0 = points[i]
            p1 = points[i+1]
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            new_points.extend([q, r])
        new_points.append(points[-1])
        points = new_points
    return points

def decode_polylines(polylines: list[str]) -> list[list[tuple[float, float]]]:
    tracks = []
    for poly in polylines:
        if not poly:
            continue
        points = pl.decode(poly)
        if points:
            # Apply smoothing to summary polylines so they don't look as jagged
            tracks.append(smooth_track(points))
    return tracks"""

src = re.sub(r"def decode_polylines\(.*?\)\s*->\s*list\[list\[tuple\[float, float\]\]\]:.*?return tracks", smoothing_code, src, flags=re.DOTALL)

with open("components/map_view.py", "w") as f:
    f.write(src)
