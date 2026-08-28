import re
with open("components/map_view.py", "r") as f:
    src = f.read()

new_draw_markers = """def draw_markers(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    project_fn,
    markers: list[MapMarker],
) -> None:
    fnt = font(MARKER_LABEL_SIZE)
    cap_top = fnt.getbbox("M")[1]
    cap_h = fnt.getbbox("M")[3] - cap_top
    seen_start = False
    placed: list[tuple[float, float, float, float]] = []

    for marker in markers:
        x, y = project_fn(marker.lat, marker.lon)
        if marker.is_start_end and not seen_start:
            draw.ellipse([x - MARKER_RADIUS, y - MARKER_RADIUS, x + MARKER_RADIUS, y + MARKER_RADIUS], fill=BLACK)
            seen_start = True
        elif marker.is_start_end:
            r = MARKER_RADIUS - 1
            draw.rectangle([x - r, y - r, x + r, y + r], fill=WHITE, outline=BLACK, width=2)
        else:
            draw.rectangle([x - 2, y - 2, x + 2, y + 2], fill=BLACK)

        if not getattr(marker, 'label', None):
            continue

        text = marker.label.upper()
        label_x = x + MARKER_RADIUS + 4
        label_y = y - cap_h / 2
        width = tracked_width(draw, text, fnt, MARKER_LABEL_TRACKING)
        for _ in range(len(placed) + 1):
            rect = (label_x, label_y, label_x + width, label_y + cap_h)
            if not any(_overlaps(rect, other) for other in placed):
                break
            label_y += cap_h + 4
        placed.append((label_x, label_y, label_x + width, label_y + cap_h))
        draw_tracked(draw, (label_x, label_y - cap_top), text, fnt, BLACK, MARKER_LABEL_TRACKING)"""

src = re.sub(r"def draw_markers\(.*?\)\s*->\s*None:.*?def _overlaps", new_draw_markers + "\n\n\ndef _overlaps", src, flags=re.DOTALL)

with open("components/map_view.py", "w") as f:
    f.write(src)
