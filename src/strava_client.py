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


if __name__ == "__main__":
    # Smoke test
    client = StravaClient()
    me = client.athlete()
    print(f"Logged in as: {me['firstname']} {me['lastname']}")
    print(f"Bikes: {len(me.get('bikes', []))}")

    print("\nRecent activities:")
    for act in client.activities(per_page=5):
        print(f"  [{act['type']:20s}] {act['name'][:40]:40s} {act['distance']/1000:6.1f} km")
