"""Unit tests for strava_client's rate-limit throttling and 429 retry logic.

Network-free: requests.request and time.sleep are patched with
unittest.mock.patch (a plain context manager, not a pytest fixture) so these
tests run under both pytest and this repo's own zero-argument __main__
runner. StravaClient is built via __new__ to skip __init__'s config.load()
and token-refresh, which need a real config.json + network.
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

import strava_client
from strava_client import StravaClient


def _fake_client() -> StravaClient:
    client = StravaClient.__new__(StravaClient)
    client.cfg = {"strava": {
        "access_token": "fake-token", "refresh_token": "x",
        "client_id": "1", "client_secret": "x", "expires_at": 9_999_999_999,
    }}
    return client


def _fake_response(status_code, headers=None, json_body=None):
    def raise_for_status():
        if status_code >= 400:
            raise strava_client.requests.HTTPError(
                f"{status_code} error", response=SimpleNamespace(status_code=status_code))
    return SimpleNamespace(
        status_code=status_code,
        headers=headers or {},
        json=lambda: {} if json_body is None else json_body,
        raise_for_status=raise_for_status,
    )


def _reset_budget():
    StravaClient._request_count = 0
    StravaClient._request_window_start = time.time()


def test_throttle_no_sleep_when_window_already_elapsed():
    _reset_budget()
    client = _fake_client()
    StravaClient._request_count = strava_client.RATE_LIMIT_SOFT_CAP
    StravaClient._request_window_start = time.time() - strava_client.RATE_LIMIT_WINDOW_SECONDS - 1

    with patch.object(strava_client.time, "sleep") as mock_sleep:
        client._throttle()

    mock_sleep.assert_not_called()
    assert StravaClient._request_count == 1  # reset then incremented


def test_throttle_sleeps_remaining_window_when_cap_hit_early():
    _reset_budget()
    client = _fake_client()
    StravaClient._request_count = strava_client.RATE_LIMIT_SOFT_CAP
    StravaClient._request_window_start = time.time()  # window just started

    with patch.object(strava_client.time, "sleep") as mock_sleep:
        client._throttle()

    mock_sleep.assert_called_once()
    (waited,), _ = mock_sleep.call_args
    assert abs(waited - strava_client.RATE_LIMIT_WINDOW_SECONDS) < 2
    assert StravaClient._request_count == 1


def test_throttle_no_pause_below_soft_cap():
    _reset_budget()
    client = _fake_client()
    StravaClient._request_count = strava_client.RATE_LIMIT_SOFT_CAP - 5

    with patch.object(strava_client.time, "sleep") as mock_sleep:
        client._throttle()

    mock_sleep.assert_not_called()
    assert StravaClient._request_count == strava_client.RATE_LIMIT_SOFT_CAP - 4


def test_429_is_retried_once_then_succeeds():
    _reset_budget()
    client = _fake_client()
    responses = [
        _fake_response(429, headers={"Retry-After": "2"}),
        _fake_response(200, json_body={"ok": True}),
    ]
    calls = []

    def fake_request(method, url, headers=None, params=None, timeout=None):
        calls.append(url)
        return responses.pop(0)

    with patch.object(strava_client.requests, "request", side_effect=fake_request), \
         patch.object(strava_client.time, "sleep") as mock_sleep:
        result = client._get("/athlete")

    assert result == {"ok": True}
    assert len(calls) == 2, "expected the original call plus exactly one retry"
    mock_sleep.assert_called_once_with(2.0)  # honored Retry-After header


def test_429_without_retry_after_uses_window_fallback_and_raises_if_still_429():
    _reset_budget()
    client = _fake_client()
    responses = [_fake_response(429), _fake_response(429)]

    with patch.object(strava_client.requests, "request", side_effect=lambda *a, **k: responses.pop(0)), \
         patch.object(strava_client.time, "sleep") as mock_sleep:
        try:
            client._get("/athlete")
            assert False, "expected HTTPError after exhausting the single 429 retry"
        except strava_client.requests.HTTPError:
            pass

    mock_sleep.assert_called_once_with(strava_client.RATE_LIMIT_WINDOW_SECONDS)


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
