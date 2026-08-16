"""Minimal Strava API client using requests.

No stravalib dependency (that pulls in pydantic-core which requires Rust
compilation on ARMv6 - unfeasible on Pi Zero).

Handles OAuth token refresh transparently.
"""
import time
import requests

import config

STRAVA_TOKEN_URL = "https://www.strava.com/api/v3/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    def __init__(self):
        self.cfg = config.load()
        self._ensure_valid_token()

    def _ensure_valid_token(self) -> None:
        """Refresh access token if expired or expiring within 60s."""
        strava = self.cfg["strava"]
        now = int(time.time())

        if strava.get("expires_at", 0) - 60 > now:
            return  # Token still valid

        print("Refreshing access token...")
        resp = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": strava["client_id"],
                "client_secret": strava["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": strava["refresh_token"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        strava["access_token"] = data["access_token"]
        strava["refresh_token"] = data["refresh_token"]
        strava["expires_at"] = data["expires_at"]
        config.save(self.cfg)
        print(f"Token refreshed, expires in {data['expires_in']}s")

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """GET call against Strava API with auth header."""
        self._ensure_valid_token()
        headers = {"Authorization": f"Bearer {self.cfg['strava']['access_token']}"}
        resp = requests.get(
            f"{STRAVA_API_BASE}{path}",
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def athlete(self) -> dict:
        """Get authenticated athlete profile."""
        return self._get("/athlete")

    def activities(self, per_page: int = 30) -> list:
        """Get recent activities (default: last 30)."""
        return self._get("/athlete/activities", params={"per_page": per_page})

    def activity(self, activity_id: int) -> dict:
        """Get single activity with full details (needed for full polyline)."""
        return self._get(f"/activities/{activity_id}")

    def activities_since(self, after_timestamp: int, per_page: int = 100) -> list:
        """Get all activities since a UNIX timestamp, paginated.

        Strava returns max 200 per page. We iterate until we get less than
        per_page results (meaning we've hit the end).
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
        """Get streams (raw datapoints) for an activity.

        Common keys: 'altitude', 'distance', 'latlng', 'heartrate',
        'watts', 'time', 'velocity_smooth', 'grade_smooth'.

        Returns dict keyed by stream type, each value is {'data': [...], ...}.
        """
        if keys is None:
            keys = ["altitude", "distance"]
        return self._get(
            f"/activities/{activity_id}/streams",
            params={"keys": ",".join(keys), "key_by_type": "true"},
        )


if __name__ == "__main__":
    # Smoke test
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

    # Test YTD fetch
    from datetime import datetime
    year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
    ytd = client.activities_since(year_start, per_page=100)
    print(f"\nYTD activities: {len(ytd)}")

    types = {}
    for a in ytd:
        t = a.get("sport_type") or a.get("type")
        types[t] = types.get(t, 0) + 1
    print(f"By type: {types}")

    print(f"\nStreams for latest activity ({latest_id}):")
    streams = client.activity_streams(latest_id)
    for key, stream in streams.items():
        data = stream.get("data", [])
        print(f"  {key:15s} {len(data)} points, first: {data[0]:.1f}, last: {data[-1]:.1f}")
