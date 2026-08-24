"""Tests for app.py's cache-fallback behavior on a failed refresh round.

CRITICAL requirement (rate-limit fix): a failed render round - e.g. Strava
429s the shared fetch - must NOT replace a good cached PNG with an error
screen. The Pi should keep seeing the last good PNG; a 429 backoff should be
invisible to it. The only exceptions are a cold cache (never succeeded) or a
cached entry older than STALE_THRESHOLD_SECONDS (1h) - at that point stale
stops being useful and the error screen is the more honest answer.

Network-free: _refresh_one is called directly with shared=None and a
simulated exception, exactly how refresh_all() invokes it when the round's
single shared Strava fetch fails - no real Strava calls happen.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

import app


def _simulated_429() -> requests.HTTPError:
    """A real requests.HTTPError with a 429 response, matching what a Strava
    rate-limit failure actually looks like by the time it reaches _refresh_one."""
    resp = requests.Response()
    resp.status_code = 429
    return requests.HTTPError("429 Too Many Requests", response=resp)


def _reset_cache():
    app._cache.clear()
    app._placeholder_keys.clear()


def test_fresh_cache_survives_a_failed_round():
    _reset_cache()
    good_png = b"GOOD_PNG_BYTES"
    app._cache["weekly"] = app.CacheEntry(png=good_png, generated_at=datetime.now(timezone.utc))

    asyncio.run(app._refresh_one("weekly", shared=None, fetch_exc=_simulated_429()))

    assert app._cache["weekly"].png == good_png, \
        "a 429 must not overwrite a good, fresh cache entry"


def test_cache_just_under_stale_threshold_survives():
    _reset_cache()
    good_png = b"GOOD_PNG_BYTES"
    recent = datetime.now(timezone.utc) - timedelta(seconds=app.STALE_THRESHOLD_SECONDS - 60)
    app._cache["weekly"] = app.CacheEntry(png=good_png, generated_at=recent)

    asyncio.run(app._refresh_one("weekly", shared=None, fetch_exc=_simulated_429()))

    assert app._cache["weekly"].png == good_png


def test_stale_cache_over_one_hour_is_replaced_with_error_screen():
    _reset_cache()
    old_png = b"OLD_PNG_BYTES"
    old = datetime.now(timezone.utc) - timedelta(seconds=app.STALE_THRESHOLD_SECONDS + 60)
    app._cache["weekly"] = app.CacheEntry(png=old_png, generated_at=old)

    asyncio.run(app._refresh_one("weekly", shared=None, fetch_exc=_simulated_429()))

    assert app._cache["weekly"].png != old_png, \
        "a cache entry older than 1h must not be served forever"
    assert len(app._cache["weekly"].png) > 0


def test_cold_cache_gets_an_error_screen_not_left_empty():
    _reset_cache()

    asyncio.run(app._refresh_one("weekly", shared=None, fetch_exc=_simulated_429()))

    assert "weekly" in app._cache
    assert len(app._cache["weekly"].png) > 0


def test_placeholder_cache_is_replaced_even_if_fresh():
    """A 'LADE DATEN...' placeholder is fresh by age but must still be treated
    as cold - it's not a real render, just startup filler."""
    _reset_cache()
    placeholder_png = b"PLACEHOLDER_PNG"
    app._cache["weekly"] = app.CacheEntry(png=placeholder_png, generated_at=datetime.now(timezone.utc))
    app._placeholder_keys.add("weekly")

    asyncio.run(app._refresh_one("weekly", shared=None, fetch_exc=_simulated_429()))

    assert app._cache["weekly"].png != placeholder_png


def test_successful_render_updates_cache_from_shared_data():
    """Sanity check the success path still works with the new shared-data
    signature (render(shared) instead of the old zero-arg render()).

    Deliberately gives every one of the 6 tracked weeks a nonzero activity:
    a week with distance_m == 0 - including a *historical* week, not just an
    entirely-empty overview - trips a separate pre-existing bug in
    components/bar_chart.py (a value==0 bar draws with y1 < y0, since `peak`
    falls back to 1.0 and value_to_y(0) lands exactly on the baseline, one
    pixel past the intended rect). Confirmed via direct render_bar_chart call
    - not a rare "totally inactive account" edge case, a single quiet week
    (illness, travel, bad weather) anywhere in the 6-week window is enough.
    Real bug, but in components/ - out of scope for the rate-limit fix this
    file is about (flagged separately, not fixed here); _refresh_one's
    error-screen fallback covers for it safely either way, so it doesn't
    compromise the CRITICAL requirement this file actually tests.
    """
    import data_fetcher

    # Anchor each activity to noon on the Monday of its intended week (not a
    # fixed "N days ago" offset) - that offset landed in the *previous* ISO
    # week whenever "today" happened to be a Monday, silently leaving the
    # current week at zero and reproducing the exact bug this test works
    # around instead of testing around it.
    today = datetime.now(timezone.utc).date()
    this_monday = today - timedelta(days=today.weekday())
    activities = []
    for weeks_ago in range(6):
        activity_monday = this_monday - timedelta(weeks=weeks_ago)
        ts = datetime(activity_monday.year, activity_monday.month, activity_monday.day,
                      12, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        activities.append({
            "sport_type": "Run", "type": "Run",
            "start_date": ts, "start_date_local": ts,
            "distance": 5000, "total_elevation_gain": 50, "moving_time": 1800,
            "map": {"summary_polyline": ""},
        })

    _reset_cache()
    shared = data_fetcher.SharedData(
        athlete={"firstname": "Test", "lastname": "Athlete"},
        ytd_activities=activities,
        latest_activity_detail=None,
        latest_streams=None,
        fetched_at=datetime.now(),
    )

    # Prove this is an actual successful render, not the except-branch's
    # error screen quietly satisfying a weaker "some bytes got cached" check.
    direct_png = app._render_weekly(shared)

    asyncio.run(app._refresh_one("weekly", shared=shared, fetch_exc=None))

    assert "weekly" in app._cache
    assert app._cache["weekly"].png == direct_png


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
