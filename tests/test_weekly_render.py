"""German singular/plural grammar checks for the weekly view.

'N AKTIVITÄTEN' should read '1 AKTIVITÄT' at N=1, not the plural-only form.
Two layers here:
  - a direct unit test of components.base.pluralize (the actual grammar)
  - a render-level sanity check (Step 5's explicit ask) that the current
    week's activity_count actually reaches the rendered PNG - i.e. changing
    it from 0 to 1 to 2 is not silently ignored by some caching/box-reuse bug
"""
import io
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Make server/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from aggregator import WeekStats, WeeklyOverview
from components.base import pluralize
from views.weekly import render_weekly


def test_pluralize_singular_at_count_one():
    assert pluralize(1, "AKTIVITÄT", "AKTIVITÄTEN") == "1 AKTIVITÄT"
    assert pluralize(1, "TAG", "TAGE") == "1 TAG"


def test_pluralize_plural_at_other_counts():
    assert pluralize(0, "AKTIVITÄT", "AKTIVITÄTEN") == "0 AKTIVITÄTEN"
    assert pluralize(2, "AKTIVITÄT", "AKTIVITÄTEN") == "2 AKTIVITÄTEN"
    assert pluralize(42, "AKTIVITÄT", "AKTIVITÄTEN") == "42 AKTIVITÄTEN"


def _weekly_overview(current_activity_count: int) -> WeeklyOverview:
    """6 otherwise-identical weeks; only the current week's activity_count varies."""
    monday = date(2026, 8, 17)
    weeks = []
    for i in range(6):
        start = monday - timedelta(weeks=5 - i)
        is_current = i == 5
        iso_year, iso_week, _ = start.isocalendar()
        weeks.append(WeekStats(
            iso_week=iso_week,
            year=iso_year,
            start_date=start,
            end_date=start + timedelta(days=6),
            distance_m=50_000,
            elevation_m=800,
            moving_time_s=7200,
            avg_heartrate_bpm=None,
            activity_count=current_activity_count if is_current else 3,
            days_with_activity=2,
            is_current=is_current,
        ))
    return WeeklyOverview(
        weeks=weeks,
        current_week=weeks[-1],
        avg_distance_m=50_000,
        avg_elevation_m=800,
        avg_heartrate_bpm=None,
        total_distance_m=sum(w.distance_m for w in weeks),
        total_elevation_m=sum(w.elevation_m for w in weeks),
        total_activities=sum(w.activity_count for w in weeks),
        date_range_start=weeks[0].start_date,
        date_range_end=weeks[-1].end_date,
    )


def _render_png_bytes(current_activity_count: int) -> bytes:
    overview = _weekly_overview(current_activity_count)
    img = render_weekly(overview, "Test Athlete", datetime(2026, 8, 23, 12, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_weekly_current_week_count_of_one_renders_distinctly():
    png_0 = _render_png_bytes(0)
    png_1 = _render_png_bytes(1)
    png_2 = _render_png_bytes(2)

    assert png_1 != png_0, "count=1 render is byte-identical to count=0"
    assert png_1 != png_2, "count=1 render is byte-identical to count=2"
    assert png_0 != png_2, "count=0 render is byte-identical to count=2"


def _weekly_overview_with_zero_week(zero_week_index: int) -> WeeklyOverview:
    """6 weeks, all with real distance/elevation except `zero_week_index`
    (0 = oldest, 5 = current), which has zero everything - a genuine rest/
    illness/travel week, not just count=0 with nonzero distance like
    _weekly_overview above. This is the exact shape that crashed
    render_bar_chart before the MIN_BAR_HEIGHT clamp fix."""
    monday = date(2026, 8, 17)
    weeks = []
    for i in range(6):
        start = monday - timedelta(weeks=5 - i)
        is_zero = i == zero_week_index
        iso_year, iso_week, _ = start.isocalendar()
        weeks.append(WeekStats(
            iso_week=iso_week,
            year=iso_year,
            start_date=start,
            end_date=start + timedelta(days=6),
            distance_m=0 if is_zero else 50_000,
            elevation_m=0 if is_zero else 800,
            moving_time_s=0 if is_zero else 7200,
            avg_heartrate_bpm=None,
            activity_count=0 if is_zero else 3,
            days_with_activity=0 if is_zero else 2,
            is_current=(i == 5),
        ))
    return WeeklyOverview(
        weeks=weeks,
        current_week=weeks[-1],
        avg_distance_m=sum(w.distance_m for w in weeks[:-1]) / 5,
        avg_elevation_m=sum(w.elevation_m for w in weeks[:-1]) / 5,
        avg_heartrate_bpm=None,
        total_distance_m=sum(w.distance_m for w in weeks),
        total_elevation_m=sum(w.elevation_m for w in weeks),
        total_activities=sum(w.activity_count for w in weeks),
        date_range_start=weeks[0].start_date,
        date_range_end=weeks[-1].end_date,
    )


def test_weekly_view_renders_with_a_zero_activity_historical_week():
    """Regression test for the bar_chart y1<y0 crash: a historical (not
    current) week with zero activity used to crash the whole weekly view."""
    overview = _weekly_overview_with_zero_week(zero_week_index=2)
    img = render_weekly(overview, "Test Athlete", datetime(2026, 8, 23, 12, 0))
    assert img.size == (800, 480)
    assert img.mode == "1"


def test_weekly_view_renders_with_zero_activity_current_week():
    """Same crash, but for the hollow-outlined current-week bar specifically."""
    overview = _weekly_overview_with_zero_week(zero_week_index=5)
    img = render_weekly(overview, "Test Athlete", datetime(2026, 8, 23, 12, 0))
    assert img.size == (800, 480)
    assert img.mode == "1"


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
