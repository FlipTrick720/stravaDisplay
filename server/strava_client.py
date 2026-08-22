"""Minimal Strava API client using requests.

No stravalib dependency (pydantic-core requires Rust compilation on ARMv6,
which is unfeasible on Pi Zero).

Design:
- Token validity is checked once at __init__.
- Subsequent calls assume the cached token is valid.
- If a call returns 401, we refresh once and retry (transparent to caller).
- config.json is only ever written via config.save() (atomic).
"""
import time
import requests

import config

STRAVA_TOKEN_URL = "https://www.strava.com/api/v3/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Timeouts (seconds)
DEFAULT_TIMEOUT = 15
TOKEN_REFRESH_TIMEOUT = 10


class StravaAuthError(Exception):
    """Raised when auth fails and cannot be recovered (bad refresh token, etc)."""


class StravaClient:
    def __init__(self):
        self.cfg = config.load()
        # Refresh once at start if needed. All subsequent calls trust the token
        # unless they get a 401 back (see _get).
        self._refresh_if_expired()

    def _refresh_if_expired(self) -> None:
        """Refresh access token if expired or expiring within 60s."""
        strava = self.cfg["strava"]
        now = int(time.time())

        if strava.get("expires_at", 0) - 60 > now:
            return  # Still valid

        self._do_refresh()

    def _do_refresh(self) -> None:
        """Unconditional token refresh via refresh_token grant."""
        strava = self.cfg["strava"]

        resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": strava["client_id"],
                "client_secret": strava["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": strava["refresh_token"],
            },
            timeout=TOKEN_REFRESH_TIMEOUT,
        )

        if resp.status_code == 400 or resp.status_code == 401:
            # Refresh token itself is bad - user needs to re-auth
            raise StravaAuthError(
                f"Token refresh failed ({resp.status_code}): {resp.text[:200]}. "
                "Refresh token is invalid - run setup_strava.py again."
            )
        resp.raise_for_status()

        data = resp.json()
        strava["access_token"] = data["access_token"]
        strava["refresh_token"] = data["refresh_token"]
        strava["expires_at"] = data["expires_at"]
        config.save(self.cfg)  # atomic write

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """GET call against Strava API. Retries once on 401 (token expired mid-flight)."""
        return self._request("GET", path, params=params)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        _retried: bool = False,
    ) -> dict | list:
        """HTTP call with transparent token refresh on 401."""
        headers = {"Authorization": f"Bearer {self.cfg['strava']['access_token']}"}
        resp = requests.request(
            method,
            f"{STRAVA_API_BASE}{path}",
            headers=headers,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )

        # If token was invalidated server-side (e.g. revoked), retry once with fresh token
        if resp.status_code == 401 and not _retried:
            self._do_refresh()
            return self._request(method, path, params=params, _retried=True)

        resp.raise_for_status()
        return resp.json()

    def athlete(self) -> dict:
        return self._get("/athlete")

    def activities(self, per_page: int = 30) -> list:
        return self._get("/athlete/activities", params={"per_page": per_page})

    def activity(self, activity_id: int) -> dict:
        return self._get(f"/activities/{activity_id}")

    def activities_since(self, after_timestamp: int, per_page: int = 100) -> list:
        """Paginated fetch of all activities since a UNIX timestamp.

        Note: Strava returns these in ASCENDING order (oldest first) when using
        'after'. Caller should re-sort if newest-first is needed.
        """
        all_activities = []
        page = 1
        while True:
            batch = self._get(
                "/athlete/activities",
                params={
                    "after": after_timestamp,
                    "per_page": per_page,
                    "page": page,
                },
            )
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return all_activities

    def activity_streams(self, activity_id: int, keys: list[str] | None = None) -> dict:
        """Get stream data (altitude, distance, etc.) for an activity."""
        if keys is None:
            keys = ["altitude", "distance"]
        return self._get(
            f"/activities/{activity_id}/streams",
            params={"keys": ",".join(keys), "key_by_type": "true"},
        )


if __name__ == "__main__":
    client = StravaClient()
    me = client.athlete()
    print(f"Logged in as: {me['firstname']} {me['lastname']}")
    print(f"Bikes: {len(me.get('bikes', []))}")

    print("\nRecent activities:")
    latest_id = None
    for act in client.activities(per_page=5):
        print(f"  [{act['type']:20s}] {act['name'][:40]:40s} {act['distance']/1000:6.1f} km")
        if latest_id is None:
            latest_id = act["id"]

    if latest_id:
        print(f"\nStreams for latest activity ({latest_id}):")
        streams = client.activity_streams(latest_id)
        for key, stream in streams.items():
            data = stream.get("data", [])
            print(f"  {key:15s} {len(data)} points, first: {data[0]:.1f}, last: {data[-1]:.1f}")
