"""Tests for aggregator category selection and weekly-bucketing logic."""
import sys
from datetime import date, datetime
from pathlib import Path

# Make server/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from aggregator import build_overview, build_weekly, categorize, CATEGORY_MAP


def _act(sport_type: str, start_date: str = "2026-08-15T10:00:00Z", **extra) -> dict:
    """Build a minimal activity dict for tests."""
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


def test_categorize_known_types():
    assert categorize({"sport_type": "MountainBikeRide"}) == "MTB"
    assert categorize({"sport_type": "Ride"}) == "Road"
    assert categorize({"sport_type": "BackcountrySki"}) == "Ski"
    assert categorize({"sport_type": "Hike"}) == "Hike"


def test_categorize_unknown_falls_through_to_other():
    assert categorize({"sport_type": "Yoga"}) == "Other"
    assert categorize({"sport_type": ""}) == "Other"
    assert categorize({}) == "Other"


def test_categorize_falls_back_to_type_field():
    """Older Strava API responses used 'type' instead of 'sport_type'."""
    assert categorize({"type": "Ride"}) == "Road"


def test_build_overview_picks_two_most_recent_categories():
    activities = [
        _act("MountainBikeRide", "2026-08-15T10:00:00Z"),  # newest
        _act("MountainBikeRide", "2026-08-14T10:00:00Z"),
        _act("BackcountrySki", "2026-02-01T10:00:00Z"),
        _act("Ride", "2026-01-15T10:00:00Z"),  # oldest
    ]
    overview = build_overview(activities)
    cats = [c.category for c in overview.categories]
    assert cats == ["MTB", "Ski"], f"Expected [MTB, Ski], got {cats}"


def test_build_overview_ignores_other_category():
    """Yoga is not in CATEGORY_MAP, must not appear as a panel."""
    activities = [
        _act("Yoga", "2026-08-15T10:00:00Z"),  # newest but Other
        _act("MountainBikeRide", "2026-08-14T10:00:00Z"),
        _act("Ride", "2026-08-13T10:00:00Z"),
    ]
    overview = build_overview(activities)
    cats = [c.category for c in overview.categories]
    assert "Other" not in cats
    assert cats == ["MTB", "Road"]


def test_build_overview_handles_only_one_category():
    """If user has only ever done MTB, we still get 2 panels (duplicated)."""
    activities = [_act("MountainBikeRide") for _ in range(5)]
    overview = build_overview(activities)
    assert len(overview.categories) == 2


def test_build_overview_aggregates_stats_correctly():
    activities = [
        _act("MountainBikeRide", distance=10000, total_elevation_gain=100, moving_time=1800),
        _act("MountainBikeRide", distance=15000, total_elevation_gain=200, moving_time=2700),
        _act("BackcountrySki", distance=5000, total_elevation_gain=500, moving_time=3600),
    ]
    overview = build_overview(activities)
    mtb = next(c for c in overview.categories if c.category == "MTB")
    assert mtb.count == 2
    assert mtb.distance_m == 25000
    assert mtb.elevation_m == 300
    assert mtb.moving_time_s == 4500


def test_build_overview_last_activity_is_newest():
    activities = [
        _act("MountainBikeRide", "2026-08-15T10:00:00Z", name="Newest"),
        _act("MountainBikeRide", "2026-08-14T10:00:00Z", name="Older"),
    ]
    overview = build_overview(activities)
    assert overview.last_activity["name"] == "Newest"


def test_build_overview_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        build_overview([])


# =========================
# build_weekly
# =========================

# Thursday of ISO week 34, 2026 -> current week is Mon 2026-08-17 .. Sun 2026-08-23.
NOW = datetime(2026, 8, 20, 12, 0, 0)


def test_build_weekly_returns_six_weeks():
    overview = build_weekly([], now=NOW)
    assert len(overview.weeks) == 6
    assert overview.current_week is overview.weeks[-1]


def test_build_weekly_monday_sunday_bucketing():
    activities = [
        _act("Run", "2026-08-17T00:01:00Z", name="Monday 00:01, current week"),
        _act("Run", "2026-08-23T23:59:00Z", name="Sunday 23:59, current week"),
        _act("Run", "2026-08-16T23:59:00Z", name="Sunday 23:59, previous week"),
        _act("Run", "2026-08-24T00:01:00Z", name="Next Monday, out of range"),
    ]
    overview = build_weekly(activities, now=NOW)

    current = overview.current_week
    assert current.start_date == date(2026, 8, 17)
    assert current.end_date == date(2026, 8, 23)
    assert current.activity_count == 2

    previous = overview.weeks[-2]
    assert previous.end_date == date(2026, 8, 16)
    assert previous.activity_count == 1

    # 2026-08-24 falls outside the 6-week window entirely - dropped, not
    # miscounted into either neighboring week.
    assert overview.total_activities == 3


def test_build_weekly_current_week_flagged():
    overview = build_weekly([], now=NOW)
    for week in overview.weeks[:-1]:
        assert week.is_current is False
    assert overview.weeks[-1].is_current is True
    assert overview.current_week.iso_week == 34
    assert overview.current_week.year == 2026


def test_build_weekly_avg_excludes_current_week():
    activities = [
        # Current week: huge distance that must NOT pull the average up.
        _act("Ride", "2026-08-18T10:00:00Z", distance=999_000),
        # Previous completed week (Mon 2026-08-10 .. Sun 2026-08-16).
        _act("Ride", "2026-08-11T10:00:00Z", distance=20_000, total_elevation_gain=400),
    ]
    overview = build_weekly(activities, now=NOW)

    # Only 1 of the 5 previous weeks has activity (20km); the other 4 count
    # as 0, per the "zero weeks still count in the average" rule.
    assert overview.avg_distance_m == 20_000 / 5
    assert overview.avg_elevation_m == 400 / 5
    assert overview.current_week.distance_m == 999_000


def test_build_weekly_empty_activities_returns_six_weeks_of_zeros():
    overview = build_weekly([], now=NOW)
    assert len(overview.weeks) == 6
    for week in overview.weeks:
        assert week.distance_m == 0
        assert week.elevation_m == 0
        assert week.activity_count == 0
        assert week.avg_heartrate_bpm is None
    assert overview.avg_distance_m == 0
    assert overview.avg_elevation_m == 0
    assert overview.avg_heartrate_bpm is None
    assert overview.total_activities == 0
    assert overview.date_range_start == date(2026, 7, 13)
    assert overview.date_range_end == date(2026, 8, 23)


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
