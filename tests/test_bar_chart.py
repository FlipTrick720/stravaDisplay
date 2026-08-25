"""Regression tests for the render_bar_chart zero-value-bar crash.

Bug: a bar with value == 0 made value_to_y() return exactly `baseline`, and
since the MIN_BAR_HEIGHT clamp only applied `if bar.value > 0`, the resulting
rect was [x0, baseline, x1, baseline - 1] - y1 < y0, which PIL's
ImageDraw.rectangle rejects with "ValueError: y1 must be greater than or
equal to y0". Real-world trigger: any week with zero activity (illness,
travel, rest week) in the weekly view's 6-week window, including the
hollow-outlined current-week bar.

Fix: the MIN_BAR_HEIGHT clamp now applies unconditionally, so a value == 0
bar draws a minimal visible tick at the baseline instead of a degenerate rect.

Each test just needs to confirm render_bar_chart doesn't raise and produces a
real image; the geometry fix itself is the same one code path regardless of
which bars are zero, so these are deliberately not pixel-inspecting - that
would just be re-testing PIL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from components.base import demo_canvas
from components.bar_chart import BarData, render_bar_chart

CANVAS_W, CANVAS_H = 600, 200
BOX = (16, 14, CANVAS_W - 16, CANVAS_H - 20)


def _render(bars, avg_line=None):
    """Draws into a fresh canvas and returns it. Raises if render_bar_chart
    raises - that's the actual thing every test here is checking."""
    img, d = demo_canvas(CANVAS_W, CANVAS_H)
    render_bar_chart(d, BOX, bars, avg_line=avg_line,
                     x_axis_label="Test", y_axis_label="Werte")
    return img


def _assert_valid_png(img):
    import io
    assert img.size == (CANVAS_W, CANVAS_H)
    assert img.mode == "1"
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # raises if PIL considers the image invalid
    assert buf.tell() > 0


def test_all_bars_zero():
    bars = [BarData(f"KW {29 + i}", 0) for i in range(6)]
    img = _render(bars, avg_line=0)
    _assert_valid_png(img)


def test_all_bars_zero_including_hollow_current_week():
    bars = [BarData(f"KW {29 + i}", 0, i == 5) for i in range(6)]
    img = _render(bars, avg_line=0)
    _assert_valid_png(img)


def test_mix_of_zero_and_nonzero_bars():
    bars = [
        BarData("KW 29", 128), BarData("KW 30", 0), BarData("KW 31", 164),
        BarData("KW 32", 0), BarData("KW 33", 148), BarData("KW 34", 88, True),
    ]
    img = _render(bars, avg_line=90)
    _assert_valid_png(img)


def test_only_current_week_hollow_bar_is_zero():
    bars = [
        BarData("KW 29", 128), BarData("KW 30", 96), BarData("KW 31", 164),
        BarData("KW 32", 42), BarData("KW 33", 148), BarData("KW 34", 0, True),
    ]
    img = _render(bars, avg_line=116)
    _assert_valid_png(img)


def test_all_bars_same_nonzero_value():
    """peak == every bar's value - value_to_y(v) == bar_area_top for all of
    them. Not observed to crash, but explicitly requested as a regression
    guard since it's the same scaling math family as the zero-value bug."""
    bars = [BarData(f"KW {29 + i}", 100, i == 5) for i in range(6)]
    img = _render(bars, avg_line=100)
    _assert_valid_png(img)


def test_single_zero_value_hollow_bar_alone():
    """Smallest possible reproduction: one bar, hollow, value 0."""
    img = _render([BarData("KW 34", 0, True)])
    _assert_valid_png(img)


def test_negative_value_does_not_crash():
    """Not expected from real Strava data (distance/elevation sums are never
    negative), but value_to_y's scaling math has the same shape for v < 0 as
    for v == 0 - worth pinning down defensively since it's the same fix."""
    bars = [BarData("KW 29", 128), BarData("KW 30", -5), BarData("KW 31", 164)]
    img = _render(bars, avg_line=90)
    _assert_valid_png(img)


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
