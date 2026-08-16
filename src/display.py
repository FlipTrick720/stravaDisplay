"""Main loop: fetch Strava data, render, push to e-paper display.

Rotation logic:
- Default view: overview (year stats + heatmaps per category)
- If last activity is within RECENT_ACTIVITY_HOURS: alternate between
  overview and latest-activity view each refresh cycle
- On any error: render Windows-XP style error screen

Refresh cadence: REFRESH_INTERVAL_SECONDS (default 5 min from config)
"""
import logging
import sys
import time
from datetime import datetime, timezone

import requests

import config
import strava_client
import aggregator
import renderer
import error_messages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("display")


# Show latest-activity view if last ride is within this window
RECENT_ACTIVITY_HOURS = 3

# Default refresh interval if not set in config
DEFAULT_REFRESH_SECONDS = 300


def _is_recent(activity: dict, hours: int) -> bool:
    """Check if activity was completed within the last N hours."""
    dt = datetime.fromisoformat(activity["start_date"].replace("Z", "+00:00"))
    # Add moving_time so 'end of activity' is our reference, not start
    end_time = dt.timestamp() + activity.get("moving_time", 0)
    return (datetime.now(timezone.utc).timestamp() - end_time) < hours * 3600


def _fetch_and_render(client: strava_client.StravaClient, show_latest: bool):
    """Fetch data + build image. Raises on any failure."""
    if show_latest:
        log.info("Rendering LATEST view")
        activities = client.activities(per_page=1)
        if not activities:
            raise ValueError("no_activities")
        activity_id = activities[0]["id"]
        activity = client.activity(activity_id)
        streams = client.activity_streams(activity_id)
        return renderer.render_dashboard(activity, streams)
    else:
        log.info("Rendering OVERVIEW view")
        year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
        activities = client.activities_since(year_start, per_page=100)
        if not activities:
            raise ValueError("no_activities")
        overview = aggregator.build_overview(activities)
        athlete = client.athlete()
        name = f"{athlete['firstname']} {athlete['lastname']}"
        return renderer.render_overview(overview, name)


def _render_error_for_exception(exc: Exception):
    """Map exception type to error category and render."""
    tech = f"{type(exc).__name__}: {exc}"[:200]

    if isinstance(exc, requests.ConnectionError) or isinstance(exc, requests.Timeout):
        category = "network"
    elif isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response else 0
        if status == 401:
            category = "auth"
        elif status == 429:
            category = "rate_limit"
        elif 500 <= status < 600:
            category = "network"
        else:
            category = "generic"
    elif isinstance(exc, ValueError) and str(exc) == "no_activities":
        category = "no_activities"
    else:
        category = "generic"

    heading, message = error_messages.get_error(category)
    log.warning("Rendering error screen: category=%s, tech=%s", category, tech)
    return renderer.render_error(
        error_message=message,
        heading=heading,
        technical_details=tech,
    )


def _push_to_display(img):
    """Send PIL Image to the Waveshare e-paper display.

    Import inside function so we can develop/test without hardware
    (fails gracefully in WSL where waveshare_epd isn't installed).
    """
    from waveshare_epd import epd7in5_V2

    epd = epd7in5_V2.EPD()
    epd.init()
    epd.display(epd.getbuffer(img))
    epd.sleep()


def main_loop():
    """Fetch → render → display → sleep → repeat."""
    cfg = config.load()
    refresh_s = cfg.get("display", {}).get(
        "refresh_interval_seconds", DEFAULT_REFRESH_SECONDS
    )
    log.info("Starting main loop, refresh every %ds", refresh_s)

    # Alternates each cycle when we have a recent activity
    show_latest_next = False

    while True:
        cycle_start = time.time()

        try:
            client = strava_client.StravaClient()

            # Check if we're in "recent activity" mode
            latest_list = client.activities(per_page=1)
            has_recent = bool(latest_list) and _is_recent(
                latest_list[0], RECENT_ACTIVITY_HOURS
            )

            # Decide which view to show
            if has_recent:
                show_this_cycle = show_latest_next
                show_latest_next = not show_latest_next  # toggle for next cycle
            else:
                show_this_cycle = False  # always overview when no recent
                show_latest_next = False  # reset toggle

            img = _fetch_and_render(client, show_latest=show_this_cycle)

        except Exception as e:
            log.exception("Error during fetch/render, showing error screen")
            try:
                img = _render_error_for_exception(e)
            except Exception:
                log.exception("Error rendering the error screen (yes really)")
                time.sleep(refresh_s)
                continue

        try:
            _push_to_display(img)
        except Exception:
            log.exception("Error pushing to display")

        elapsed = time.time() - cycle_start
        sleep_for = max(0, refresh_s - elapsed)
        log.info("Cycle took %.1fs, sleeping %.1fs", elapsed, sleep_for)
        time.sleep(sleep_for)


if __name__ == "__main__":
    # CLI: allow "once" mode for testing without infinite loop
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        cfg = config.load()
        try:
            client = strava_client.StravaClient()
            latest = client.activities(per_page=1)
            has_recent = bool(latest) and _is_recent(latest[0], RECENT_ACTIVITY_HOURS)
            log.info("Recent activity within %dh: %s", RECENT_ACTIVITY_HOURS, has_recent)
            img = _fetch_and_render(client, show_latest=has_recent)
        except Exception as e:
            log.exception("Error, rendering error screen")
            img = _render_error_for_exception(e)

        img.save("preview_display.png")
        log.info("Saved preview_display.png (skipping actual display push)")
    else:
        main_loop()
