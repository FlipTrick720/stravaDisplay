"""Visual regression checks for the overview view: canvas bounds and margins.

Guards against a real bug found in Phase 2 Step 3 review: the bottom-right
footer's vertical position was computed from a single glyph's ("M") bbox
instead of the actual string's, under-measuring its ascent by 2px and pushing
the last row of ink 1px past the 480px canvas edge - not visibly "clipped"
(PIL just silently drops rows outside the image), but zero whitespace margin
either way.
"""
import sys
from datetime import datetime
from pathlib import Path

# Make server/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from aggregator import build_overview
from views.overview import render_overview

MIN_BOTTOM_MARGIN = 4  # px, per Step 3 fix request


def _act(sport_type: str, start_date: str, **extra) -> dict:
    return {
        "sport_type": sport_type,
        "type": sport_type,
        "start_date": start_date,
        "start_date_local": start_date,
        "name": f"Test {sport_type}",
        "distance": 10000,
        "total_elevation_gain": 200,
        "moving_time": 3600,
        "map": {"summary_polyline": ""},
        **extra,
    }


def _render_test_overview():
    activities = [
        _act("MountainBikeRide", "2026-08-15T10:00:00Z",
             name="Nockspitze Feierabendrunde", distance=42100,
             total_elevation_gain=980, moving_time=2 * 3600 + 48 * 60),
        _act("MountainBikeRide", "2026-08-01T10:00:00Z"),
        _act("BackcountrySki", "2026-02-01T10:00:00Z"),
        _act("BackcountrySki", "2026-01-15T10:00:00Z"),
    ]
    overview = build_overview(activities, year=2026)
    return render_overview(overview, "Test Athlete", datetime(2026, 8, 23, 14, 35))


def test_render_overview_canvas_is_exactly_800x480():
    img = _render_test_overview()
    assert img.size == (800, 480), f"expected (800, 480), got {img.size}"


def test_render_overview_bottom_row_has_whitespace_margin():
    from views.overview import DIVIDER_X
    img = _render_test_overview()
    px = img.convert("L").load()
    w, h = img.size

    for offset in range(MIN_BOTTOM_MARGIN):
        y = h - 1 - offset
        dark = [x for x in range(w) if px[x, y] < 128 and x != DIVIDER_X]
        assert not dark, (
            f"row {y} (only {offset}px above the bottom edge) has ink at "
            f"x={dark[:5]}... - need at least {MIN_BOTTOM_MARGIN}px of "
            f"whitespace below the last text"
        )


def test_render_overview_vertical_divider_present():
    """1px black divider between the two category panels, full content height."""
    from views.overview import BOTTOM_ROW_Y0, DIVIDER_X, HEADER_HEIGHT

    img = _render_test_overview()
    px = img.convert("L").load()

    dark_rows = sum(
        1 for y in range(HEADER_HEIGHT, BOTTOM_ROW_Y0)
        if px[DIVIDER_X, y] < 128
    )
    total_rows = BOTTOM_ROW_Y0 - HEADER_HEIGHT
    assert dark_rows == total_rows, (
        f"divider at x={DIVIDER_X} is dark for {dark_rows}/{total_rows} rows, "
        "expected a solid line spanning the full panel height"
    )


if __name__ == "__main__":
    # Simple runner if pytest is not installed
    import traceback
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
