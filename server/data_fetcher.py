"""Single coordinated Strava fetch shared by all 3 live views.

Each view used to fetch its own data independently during the background
cache refresh:
  weekly:   activities_since(6 weeks) + athlete()          ~2-3 calls
  overview: activities_since(year start) + athlete()       ~2-3 calls
  activity: activities(1) + activity(id) + streams(id) + athlete()  4 calls

That's ~7-8 Strava API calls per refresh round. At the old 240s refresh
interval that's ~105 calls/hour - over Strava's 100 requests/15min cap (see
app.py's CACHE_REFRESH_SECONDS for the other half of this fix).

fetch_all() gets everything all 3 views need in ONE pass (4-5 calls), and
app.py's refresh loop calls it once per round and hands the same SharedData
to all 3 renderers - they no longer talk to Strava at all.
"""
from datetime import datetime
from typing import NamedTuple

from strava_client import StravaClient


class SharedData(NamedTuple):
    athlete: dict
    ytd_activities: list[dict]            # all activities since Jan 1, ASC order (Strava's after= order)
    latest_activity_detail: dict | None   # full detail (incl. map.polyline) of the newest YTD activity
    latest_streams: dict | None           # altitude + distance + heartrate for that same activity
    fetched_at: datetime


def fetch_all(client: StravaClient) -> SharedData:
    """4-5 Strava API calls total:

      1. athlete()
      2. activities_since(year_start) - 1-2 calls, paginated at per_page=100
      3. activity(latest_id)   - full detail, skipped if there are no YTD activities
      4. activity_streams(latest_id) - skipped alongside #3

    Known edge case, accepted rather than worked around with a 6th call:
    ytd_activities only reaches back to Jan 1 of the current year. In the
    first ~6 weeks of a new year, build_weekly() (called on this same list
    by app.py) won't see activities from December, and if nothing has been
    logged yet this year, "latest activity" comes back None even though a
    real most-recent activity exists from last December. Dormant for the
    other ~46 weeks of the year; not worth doubling the request budget to
    close a January-only gap.
    """
    athlete = client.athlete()

    year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
    ytd_activities = client.activities_since(year_start, per_page=100)

    latest_activity_detail = None
    latest_streams = None
    if ytd_activities:
        latest_id = max(ytd_activities, key=lambda a: a["start_date"])["id"]
        latest_activity_detail = client.activity(latest_id)
        latest_streams = client.activity_streams(latest_id)

    return SharedData(
        athlete=athlete,
        ytd_activities=ytd_activities,
        latest_activity_detail=latest_activity_detail,
        latest_streams=latest_streams,
        fetched_at=datetime.now(),
    )
