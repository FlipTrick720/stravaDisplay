"""Verifies fetch_all() makes the coordinated 4-5 Strava calls it claims to,
not the ~7-8 the 3 views used to make independently.

Network-free: StravaClient's public methods are mocked directly (no HTTP),
so this is deterministic and safe to run without live Strava access or
burning real rate-limit budget - which matters, since this exact scenario
(counting calls per round) is hard to verify against the real API without
risking triggering the very rate limit this fix is about.
"""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

import data_fetcher


def _mock_client(ytd_activities):
    client = MagicMock()
    client.athlete.return_value = {"firstname": "Test", "lastname": "Athlete"}
    client.activities_since.return_value = ytd_activities
    client.activity.return_value = {"id": 999, "name": "Detail", "map": {"polyline": "abc"}}
    client.activity_streams.return_value = {"altitude": {"data": [1, 2]}, "distance": {"data": [0, 100]}}
    return client


def test_fetch_all_makes_four_calls_when_there_are_activities():
    activities = [
        {"id": 1, "start_date": "2026-01-05T10:00:00Z"},
        {"id": 999, "start_date": "2026-08-20T10:00:00Z"},  # newest -> should become "latest"
    ]
    client = _mock_client(activities)

    shared = data_fetcher.fetch_all(client)

    client.athlete.assert_called_once()
    client.activities_since.assert_called_once()
    client.activity.assert_called_once_with(999)  # the newest by start_date
    client.activity_streams.assert_called_once_with(999)

    total_calls = (client.athlete.call_count + client.activities_since.call_count
                   + client.activity.call_count + client.activity_streams.call_count)
    assert total_calls == 4, f"expected 4 calls (down from the old ~7-8), got {total_calls}"

    assert shared.ytd_activities == activities
    assert shared.latest_activity_detail["id"] == 999
    assert shared.latest_streams is not None
    assert isinstance(shared.fetched_at, datetime)


def test_fetch_all_skips_detail_and_stream_calls_when_no_activities():
    client = _mock_client([])

    shared = data_fetcher.fetch_all(client)

    client.athlete.assert_called_once()
    client.activities_since.assert_called_once()
    client.activity.assert_not_called()
    client.activity_streams.assert_not_called()

    assert shared.ytd_activities == []
    assert shared.latest_activity_detail is None
    assert shared.latest_streams is None


def test_fetch_all_picks_newest_by_start_date_not_list_order():
    """activities_since returns ASCENDING order (Strava's after= behavior) -
    fetch_all must not assume the last list element is newest without checking."""
    activities = [
        {"id": 111, "start_date": "2026-06-01T10:00:00Z"},
        {"id": 222, "start_date": "2026-08-01T10:00:00Z"},  # actually newest
        {"id": 333, "start_date": "2026-07-01T10:00:00Z"},  # out of order on purpose
    ]
    client = _mock_client(activities)

    data_fetcher.fetch_all(client)

    client.activity.assert_called_once_with(222)


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
