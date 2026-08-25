"""FastAPI app serving pre-rendered PNG views for the e-paper display.

The Pi fetches a PNG over HTTP and renders nothing. See CLAUDE.md
"API-first rendering" for why.

Views are NOT rendered per request. A background task re-renders everything
every CACHE_REFRESH_SECONDS into an in-memory cache, and request handlers
just hand back cached bytes. This keeps the Pi's latency flat.

One Strava fetch per round, not one per view: each of the 3 live views used
to independently fetch its own data (see data_fetcher.py's docstring for the
exact tally), which added up to ~7-8 Strava API calls per round - at the old
240s interval, ~105/hour, over Strava's 100-requests/15min cap. Now
data_fetcher.fetch_all() gets everything all 3 views need in one coordinated
pass (4-5 calls) and the views just render from that; they never touch
strava_client themselves.
"""
import asyncio
import io
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile
from PIL import Image, ImageDraw, ImageFont

import aggregator
import config as config_store  # aliased: `config` is the upload field name below
import data_fetcher
import error_messages
import strava_client
from views import render_dashboard, render_error, render_overview, render_weekly

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("app")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"

# Seconds between background render rounds. Display rotates every 5 min
# between 3 views = 15 min for a full cycle, and Strava activities don't
# change minute to minute, so there's no benefit to refreshing faster than
# that - and every round costs ~4-5 Strava API calls (see data_fetcher.py),
# so 900s keeps us at ~20/hour, well clear of Strava's 100/15min cap even
# with room for manual /admin/cache checks or a bootstrap-triggered refresh.
CACHE_REFRESH_SECONDS = 900

# Give the container's network/DNS a moment to settle and avoid a thundering
# herd of simultaneous first-fetches if Docker restarts multiple containers
# at once during a deploy.
STARTUP_DELAY_SECONDS = 10

# A failed render round keeps serving the last good PNG (stale beats an error
# screen) UNLESS it's this old - at that point stale stops being useful and
# the error screen is more honest than silently-ancient data.
STALE_THRESHOLD_SECONDS = 3600

ADMIN_TOKEN_VAR = "STRAVA_ADMIN_TOKEN"

ERROR_CATEGORIES = ("network", "auth", "overload", "no_activities", "rate_limit", "generic")
LIVE_VIEWS = ("weekly", "overview", "activity")


@dataclass
class CacheEntry:
    png: bytes
    generated_at: datetime


# view key -> CacheEntry. Error views are keyed "error:<category>".
_cache: dict[str, CacheEntry] = {}
_cache_lock = asyncio.Lock()


# =========================
# Rendering (all blocking, run via asyncio.to_thread)
# =========================

def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _centered_text_png(text: str) -> bytes:
    """Cheap placeholder image. No network, safe to build during startup."""
    img = Image.new("1", (800, 480), 1)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 28)
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((800 - (bbox[2] - bbox[0])) // 2, (480 - (bbox[3] - bbox[1])) // 2),
        text, font=font, fill=0,
    )
    return _to_png(img)


def _render_error_for_exception(exc: Exception) -> Image.Image:
    """Map exception type to error category and render the XP-style screen."""
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
    return render_error(
        error_message=message, heading=heading, technical_details=tech,
    )


def _athlete_name(shared: data_fetcher.SharedData) -> str:
    return f"{shared.athlete['firstname']} {shared.athlete['lastname']}"


def _render_weekly(shared: data_fetcher.SharedData) -> bytes:
    # build_weekly self-windows to the last 6 ISO weeks and ignores anything
    # outside that; passing the full YTD list is fine (see data_fetcher.py's
    # docstring for the January-boundary caveat this implies).
    overview = aggregator.build_weekly(shared.ytd_activities)
    return _to_png(render_weekly(overview, _athlete_name(shared), shared.fetched_at))


def _render_overview(shared: data_fetcher.SharedData) -> bytes:
    if not shared.ytd_activities:
        raise ValueError("no_activities")
    overview = aggregator.build_overview(shared.ytd_activities)
    return _to_png(render_overview(overview, _athlete_name(shared), shared.fetched_at))


def _render_activity(shared: data_fetcher.SharedData) -> bytes:
    if shared.latest_activity_detail is None:
        raise ValueError("no_activities")
    return _to_png(render_dashboard(
        shared.latest_activity_detail, shared.latest_streams,
        _athlete_name(shared), shared.fetched_at,
    ))


def _render_error_view(category: str) -> bytes:
    heading, message = error_messages.get_error(category)
    img = render_error(
        error_message=message,
        heading=heading,
        technical_details=f"Category: {category} (pre-rendered)",
    )
    return _to_png(img)


_RENDERERS = {
    "weekly": _render_weekly,
    "overview": _render_overview,
    "activity": _render_activity,
}


# =========================
# Background refresh
# =========================

async def _store(key: str, png: bytes) -> None:
    async with _cache_lock:
        _cache[key] = CacheEntry(png=png, generated_at=datetime.now(timezone.utc))


async def _fetch_shared_data() -> data_fetcher.SharedData:
    """The one Strava fetch each refresh round makes, shared by all 3 views."""
    client = strava_client.StravaClient()
    return await asyncio.to_thread(data_fetcher.fetch_all, client)


async def _refresh_one(
    key: str,
    shared: data_fetcher.SharedData | None,
    fetch_exc: Exception | None,
) -> None:
    """Re-render one view from this round's shared data. On failure keep
    whatever is already cached.

    A stale panel beats an error panel, so a failed render never overwrites a
    good entry - UNLESS the cache is cold (nothing to fall back on) or the
    cached entry is truly stale (>1h old, e.g. after a 429 backoff swallowed
    several rounds in a row): then the error screen is more honest than
    silently serving ancient data forever.
    """
    try:
        if shared is None:
            raise fetch_exc
        render = _RENDERERS[key]
        png = await asyncio.to_thread(render, shared)
        await _store(key, png)
        log.info("Rendered %s (%d bytes)", key, len(png))
    except Exception as exc:
        cached = _cache.get(key)
        is_placeholder = _is_placeholder(key)
        age = None if cached is None else _age_seconds(cached)
        is_stale = age is not None and age > STALE_THRESHOLD_SECONDS

        # Keep good cached PNG (not placeholder, not stale)
        has_good_cache = cached is not None and not is_placeholder and not is_stale

        if has_good_cache:
            log.warning("Render failed for %s (%s: %s), keeping cached PNG "
                        "(%s old, still good)",
                        key, type(exc).__name__, exc, f"{age:.0f}s")
        else:
            reason = ("Cold cache (never rendered)" if cached is None
                      else "Seeded placeholder (never successfully rendered)" if is_placeholder
                      else f"Stale cache (>{STALE_THRESHOLD_SECONDS}s old)")
            log.warning("Render failed for %s (%s: %s) — %s, showing error screen",
                        key, type(exc).__name__, exc, reason)
            png = await asyncio.to_thread(
                lambda: _to_png(_render_error_for_exception(exc))
            )
            await _store(key, png)


_placeholder_keys: set[str] = set()


def _is_placeholder(key: str) -> bool:
    return key in _placeholder_keys


def _age_seconds(entry: CacheEntry) -> float:
    return (datetime.now(timezone.utc) - entry.generated_at).total_seconds()


async def refresh_all() -> None:
    """One full render round: a single shared Strava fetch, then all 3 live
    views rendered from it, plus every error category."""
    try:
        shared = await _fetch_shared_data()
        fetch_exc = None
        log.info("Shared fetch OK: %d YTD activities, latest=%r",
                 len(shared.ytd_activities),
                 shared.latest_activity_detail and shared.latest_activity_detail.get("name"))
    except Exception as exc:
        shared = None
        fetch_exc = exc
        log.warning("Shared Strava fetch failed (%s: %s), views fall back to cache",
                    type(exc).__name__, exc)

    for key in LIVE_VIEWS:
        await _refresh_one(key, shared, fetch_exc)
        _placeholder_keys.discard(key)

    for category in ERROR_CATEGORIES:
        key = f"error:{category}"
        try:
            png = await asyncio.to_thread(_render_error_view, category)
            await _store(key, png)
        except Exception as exc:
            log.warning("Render failed for %s: %s", key, exc)


async def _refresh_loop() -> None:
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        try:
            await refresh_all()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Refresh round failed entirely")
        await asyncio.sleep(CACHE_REFRESH_SECONDS)


# =========================
# Lifespan
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get(ADMIN_TOKEN_VAR):
        raise RuntimeError(
            f"{ADMIN_TOKEN_VAR} is not set. Generate one with "
            "`openssl rand -hex 32` and put it in .env. Refusing to start: "
            "/admin/bootstrap would otherwise be unauthenticated."
        )

    # Seed placeholders so traffic can be served immediately. The first real
    # round runs in the background; blocking startup on Strava would trip the
    # compose healthcheck and delay cloudflared.
    loading = _centered_text_png("LADE DATEN...")
    for key in LIVE_VIEWS:
        _cache[key] = CacheEntry(png=loading, generated_at=datetime.now(timezone.utc))
        _placeholder_keys.add(key)
    log.info("Seeded loading placeholders, starting refresh loop (every %ds)", CACHE_REFRESH_SECONDS)

    task = asyncio.create_task(_refresh_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        log.info("Refresh loop stopped")


app = FastAPI(title="Strava Display", lifespan=lifespan)


# =========================
# Auth
# =========================

def require_admin(authorization: str | None = Header(None)) -> None:
    """Bearer token check against STRAVA_ADMIN_TOKEN."""
    expected = os.environ.get(ADMIN_TOKEN_VAR, "")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not secrets.compare_digest(authorization[len("Bearer "):], expected):
        raise HTTPException(status_code=401, detail="Invalid token")


# =========================
# Endpoints
# =========================

# FastAPI serves the same in-memory bytes to every client until the next
# background refresh round, but browsers/CDNs (Cloudflare) don't know that
# and will happily cache a PNG response on their own. The Pi always wants
# this round's bytes, and Malte needs the browser to reflect a redeploy
# immediately without manually busting cache - so every /display/*.png
# response is marked non-cacheable, deliberately overriding HTTP's default.
NO_CACHE_HEADERS = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def _cached_response(key: str, fallback_key: str | None = None) -> Response:
    entry = _cache.get(key)
    if entry is None and fallback_key:
        entry = _cache.get(fallback_key)
    if entry is None:
        # Only reachable before the first round for a view with no placeholder.
        return Response(content=_centered_text_png("LADE DATEN..."),
                        media_type="image/png", headers=NO_CACHE_HEADERS)
    return Response(
        content=entry.png,
        media_type="image/png",
        headers={**NO_CACHE_HEADERS, "X-Generated-At": entry.generated_at.isoformat()},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/display/weekly.png")
def weekly_png():
    return _cached_response("weekly")


@app.get("/display/overview.png")
def overview_png():
    return _cached_response("overview")


@app.get("/display/activity.png")
def activity_png():
    return _cached_response("activity")


@app.get("/display/error.png")
def error_png(category: str = Query("generic")):
    return _cached_response(f"error:{category}", fallback_key="error:generic")


@app.get("/admin/cache", dependencies=[Depends(require_admin)])
def cache_status():
    """Cache freshness, for debugging.

        curl -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \\
             https://strava-display.maltebraig.com/admin/cache
    """
    return {
        key: {
            "age_seconds": round(_age_seconds(entry), 1),
            "size_bytes": len(entry.png),
            "generated_at": entry.generated_at.isoformat(),
            "placeholder": _is_placeholder(key),
        }
        for key, entry in _cache.items()
    }


REQUIRED_STRAVA_KEYS = (
    "client_id", "client_secret", "access_token", "refresh_token", "expires_at",
)


@app.post("/admin/bootstrap", dependencies=[Depends(require_admin)])
async def bootstrap(config: UploadFile = File(...)):
    """Upload a config.json produced locally by setup_strava.py.

    Replaces the scp step: run OAuth on a machine with a browser, then push the
    result to the server over the tunnel.

        cd server && python3 setup_strava.py
        curl -X POST \\
             -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \\
             -F "config=@config.json" \\
             https://strava-display.maltebraig.com/admin/bootstrap

    Writes atomically to CONFIG_DIR/config.json and kicks off an immediate
    re-render rather than waiting for the next 4-minute tick.
    """
    raw = await config.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Not valid JSON: {e}")

    if not isinstance(data, dict) or not isinstance(data.get("strava"), dict):
        raise HTTPException(status_code=400, detail="Missing top-level 'strava' object")

    missing = [
        k for k in REQUIRED_STRAVA_KEYS
        if k not in data["strava"] or data["strava"][k] in ("", None)
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"strava.{{{','.join(missing)}}} missing or empty. "
                   "Run setup_strava.py to produce a complete config.json.",
        )

    try:
        config_store.save(data)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not write config: {e}")

    log.info("Config bootstrapped via /admin/bootstrap -> %s", config_store.CONFIG_PATH)

    # Fire and forget: the caller gets an answer now, renders land shortly.
    asyncio.create_task(refresh_all())

    return {"status": "ok", "next_refresh": "immediate"}
