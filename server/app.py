"""FastAPI app serving pre-rendered PNG views for the e-paper display.

Endpoints mirror the views in pi/display.py's old main loop, but here the Pi
just fetches a PNG over HTTP instead of rendering locally. See CLAUDE.md
"API-first rendering" for why.
"""
import io
from datetime import datetime

import requests
from fastapi import FastAPI, Query, Response
from PIL import Image, ImageDraw, ImageFont

import aggregator
import error_messages
import renderer
import strava_client

app = FastAPI(title="Strava Display")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _png_response(img: Image.Image) -> Response:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def _render_error_for_exception(exc: Exception) -> Image.Image:
    """Map exception type to error category and render the XP-style screen.

    Same mapping as pi/display.py's old main loop, kept in sync manually
    since there's no shared module for it (small enough to duplicate).
    """
    tech = f"{type(exc).__name__}: {exc}"[:200]

    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        category = "network"
    elif isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else 0
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
    return renderer.render_error(
        error_message=message,
        heading=heading,
        technical_details=tech,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/display/weekly.png")
def weekly_png():
    # Placeholder until Phase 2 builds the real bar-chart view.
    img = Image.new("1", (800, 480), 1)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 28)
    text = "WEEKLY VIEW - COMING SOON"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (800 - (bbox[2] - bbox[0])) // 2
    y = (480 - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), text, font=font, fill=0)
    return _png_response(img)


@app.get("/display/overview.png")
def overview_png():
    try:
        client = strava_client.StravaClient()
        year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
        activities = client.activities_since(year_start, per_page=100)
        if not activities:
            raise ValueError("no_activities")
        overview = aggregator.build_overview(activities)
        athlete = client.athlete()
        name = f"{athlete['firstname']} {athlete['lastname']}"
        img = renderer.render_overview(overview, name)
    except Exception as e:
        img = _render_error_for_exception(e)
    return _png_response(img)


@app.get("/display/activity.png")
def activity_png():
    try:
        client = strava_client.StravaClient()
        activities = client.activities(per_page=1)
        if not activities:
            raise ValueError("no_activities")
        activity_id = activities[0]["id"]
        activity = client.activity(activity_id)
        streams = client.activity_streams(activity_id)
        img = renderer.render_dashboard(activity, streams)
    except Exception as e:
        img = _render_error_for_exception(e)
    return _png_response(img)


@app.get("/display/error.png")
def error_png(category: str = Query("generic")):
    heading, message = error_messages.get_error(category)
    img = renderer.render_error(
        error_message=message,
        heading=heading,
        technical_details=f"Category: {category} (manual /display/error.png request)",
    )
    return _png_response(img)
