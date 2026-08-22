# Strava Display - Context for Claude Code

## Project

E-paper display showing Strava stats. Gift for a friend. Owner: Malte Braig (Master's SE, Uni Innsbruck, ADHD - prefers concise responses).

## Status

Phase 1 done: server skeleton, 3 PNG endpoints (2 real, weekly is a placeholder), Docker + Fly.io config. Not deployed yet, Strava config not bootstrapped on the volume yet.

Phase 2 open: real weekly view, component refactor of `renderer.py`, rewrite `pi/display.py` as thin client, extended sport categories, response caching.

Sections below marked **TARGET** describe the intended end state and are NOT implemented yet. Do not assume that code exists.

## Architecture

**Two components:**

1. **`server/`** - FastAPI app that fetches Strava data and renders PNG views
   - Runs on Fly.io (Docker deployment, primary region `fra`)
   - Domain: `strava.<mydomain>.tld` (CNAME from Spaceship DNS)
   - Serves per-view PNG endpoints (see Endpoints below)
   - Holds Strava OAuth tokens in a mounted volume at `/data`

2. **`pi/`** - Minimal Python client on Raspberry Pi Zero WH
   - Fetches PNGs from server, pushes to Waveshare 7.5" e-Paper HAT V2
   - Rotates through 3 view URLs, 5 min per view
   - systemd service for auto-start
   - **TARGET.** `pi/display.py` is currently the OLD pre-server main loop, moved verbatim from `src/`. It still does its own Strava fetching and rendering and imports `config`/`strava_client`/`aggregator`/`renderer`, which no longer sit beside it. It does not run as-is. Phase 2 replaces it with the ~40-line fetch-PNG-and-push client.

## Repo Layout

```
server/          FastAPI app + all Strava/render logic
  app.py         endpoints, exception -> error-screen mapping
  strava_client.py, aggregator.py, renderer.py, cities.py,
  config.py, error_messages.py, setup_strava.py
pi/display.py    stale old main loop, see above
tests/           pytest, adds server/ to sys.path
setup/           Pi provisioning scripts (part1 preboot, part2 postboot)
systemd/         strava-display.service
Dockerfile       python:3.11-slim, uvicorn on :8000
fly.toml         Fly.io app config, /health check, strava_config volume -> /data
config.json      secrets, gitignored. Local dev only; prod reads /data/config.json
```

## Endpoints

GET /display/weekly.png - week vs previous weeks bar chart view (**placeholder**, renders "COMING SOON")
GET /display/overview.png - year overview, 2 most-recently-used categories
GET /display/activity.png - detail of most recent activity
GET /display/error.png?category=<cat> - error screen (categories: network, auth, overload, no_activities, rate_limit, generic)
GET /health - health check for Fly.io

`overview.png` and `activity.png` never return 5xx. On any fetch/render failure they fall back to `renderer.render_error()` with the exception mapped to a category, so the Pi always gets a displayable 800x480 PNG. Mapping lives in `app.py:_render_error_for_exception` and duplicates the logic from the old `display.py`; keep the two in sync or unify them in Phase 2.

**TARGET:** server-side response caching (~5 min) to reduce Strava API load. Not implemented. Every request currently hits the Strava API, and `overview.png` paginates the full year.

## Running

```bash
# [wsl] dev server (cwd matters: config.py resolves config.json via parent.parent)
cd server && python3 -m uvicorn app:app --reload --port 8000

# [wsl] tests
python3 tests/test_aggregator.py     # or: pytest tests/

# [wsl] one-off render previews, no server
cd server && python3 renderer.py                # overview
cd server && python3 renderer.py latest         # single activity
cd server && python3 renderer.py error network  # error screen

# [wsl] OAuth setup, writes tokens into config.json
cd server && python3 setup_strava.py

# [wsl] point at a different config dir (same mechanism prod uses)
cd server && STRAVA_CONFIG_DIR=/tmp/cfg python3 -m uvicorn app:app --port 8000
```

## Config Resolution

`config.py` resolves `config.json` at import time:

```python
CONFIG_DIR  = Path(os.environ.get("STRAVA_CONFIG_DIR", Path(__file__).parent.parent))
CONFIG_PATH = CONFIG_DIR / "config.json"
```

- **Local dev:** env var unset, falls back to repo root. `setup_strava.py` and the dev server agree.
- **Fly.io:** `STRAVA_CONFIG_DIR=/data` (set in `fly.toml [env]`), pointing at the mounted volume.

Resolved at import, so the env var must be set before `config` is imported. Fine via `fly.toml`, but relevant if anything ever sets it at runtime.

This is what decouples the token store from the image. The volume must not be mounted at `/app`, which would shadow the deployed code.

## Deployment (Fly.io)

Docker mirrors the dev server: `WORKDIR /app/server` so `app.py` can import its siblings as top-level modules. That WORKDIR no longer determines where `config.json` is found; `STRAVA_CONFIG_DIR` does.

`fly.toml` essentials:
- `primary_region = "fra"` (Frankfurt, closest to AT)
- `internal_port = 8000`, matching the uvicorn CMD
- `auto_stop_machines = "stop"` + `min_machines_running = 0`, so it scales to zero between Pi polls. The Pi hits it every 5 min and eats a cold start; acceptable for an e-ink refresh, and it keeps the thing near-free.
- `[mounts] source = "strava_config", destination = "/data"`

**Not yet done:** never deployed, and the volume has no `config.json` on it. Until bootstrapped, the Strava endpoints return the XP error screen (not a 5xx) with "config.json not found at /data/config.json" in the technical details line. That message is the quickest check that the mount is live but unseeded.

Bootstrapping needs a decision: `setup_strava.py` is interactive (paste an OAuth code at a prompt), so it cannot just be run in a Fly machine as-is. Options are running OAuth locally then pushing the resulting `config.json` onto the volume, or seeding tokens from Fly secrets on first boot.

**Volume caveat:** a Fly volume is tied to one machine in one region. Scaling past a single machine means the second one gets no config, so keep this single-machine unless the token store moves elsewhere.

**Unverified:** whether the `[[http_service.checks]]` health check keeps a machine from auto-stopping. Fly's autostop docs do not address it. If the app never scales to zero after deploy, suspect the check interval first.

## Rendering Approach

All rendering is 1-bit black/white PIL (`Image.new("1", (800, 480), 1)`) - native for Waveshare 7.5" V2.

Fonts: DejaVu Sans / DejaVu Sans Bold, hardcoded to `/usr/share/fonts/truetype/dejavu/`. The Dockerfile installs `fonts-dejavu-core` for this reason. Any change to that path breaks both container and Pi.

**TARGET - component refactor.** `renderer.py` is currently monolithic per-view: `render_dashboard()`, `render_overview()`, `render_error()`, each built from private `_draw_*` helpers that are not reusable across views. Phase 2 extracts shared components:
- `header` - black bar with year + name + timestamp + STRAVA badge
- `stat_block` - big number, unit subscript, small label, optional delta%
- `map_view` - projected tracks, cities, compass, scale bar
- `bar_chart` - weekly comparison with avg line
- `badge` - category badge (MTB, SKI, etc.)
- `elevation` - dual line chart (altitude + heartrate)

Reusable today: `_project_polyline`, `_compute_global_bounds`, `_draw_cities`, `_draw_compass`, `_draw_scale_bar`, `_font`, `_wrap_text`.

## Sport Categorization

**Current** (`aggregator.CATEGORY_MAP`), 4 categories:

```python
Road: Ride, VirtualRide, EBikeRide
MTB:  MountainBikeRide, GravelRide, EMountainBikeRide
Ski:  BackcountrySki, AlpineSki, NordicSki, TourSki
Hike: Hike
```

Everything else falls through to `"Other"` and is excluded from panel selection.

**TARGET** - extend to cover all Strava activity types:

```python
Cycling: Ride, MountainBikeRide, GravelRide, VirtualRide, EBikeRide, EMountainBikeRide
Running: Run, TrailRun, VirtualRun
Ski:     AlpineSki, BackcountrySki, NordicSki, TourSki, Snowboard
Hiking:  Hike, Walk
Water:   Kayaking, StandUpPaddling, Surfing, Swim
Fitness: WeightTraining, Workout, Yoga, HIIT
Winter:  IceSkate, RollerSki
```

Note this reshapes existing categories (Road+MTB collapse into Cycling), so `tests/test_aggregator.py` expectations change with it.

Overview shows 2 most-recently-used categories. Activities sorted newest-first internally (Strava `?after=` returns ASC, must resort).

## Key Technical Decisions

**No stravalib** - pydantic-core requires Rust, unfeasible on ARMv6 Pi Zero. Not relevant server-side but keep for consistency. Use `requests` directly with our thin StravaClient wrapper.

**API-first rendering** - Pi renders nothing. All logic on server. Design iteration = browser refresh, not Pi reflash. Handover to recipient = one URL, no SSH needed on Pi.

**No dithering** - Direct 1-bit rendering. Dithering looks muddy on e-ink with thin lines.

**No tile-based maps** - Cities from static list + compass + scale bar instead. OpenTopoMap etc. don't 1-bit well.

**Atomic config writes** - `write to tempfile, fsync, os.replace`. Non-atomic writes corrupt config.json on power loss (real risk with token refresh every 6h).

**Token refresh** - Once at client init, not per API call. Retry once on 401 with recursion guard.

**Cluster filter for heatmaps** - Bucket tracks by 0.2° cells, keep only densest 3x3 cell area + last 15 activities. Handles "one ride in Spain kills local zoom" problem.

## Design Language

Swiss/editorial:
- Heavy black bars for headers/badges
- Big bold numbers with small unit subscripts
- UPPERCASE labels
- Thin dashed lines for reference/averages
- Clear typographic hierarchy

## Design Mocks

Reference designs live at repo root, NOT in `docs/mocks/`:
- `designActivity.png` - single activity detail
- `designOverview.png` - year overview with 2 category panels
- `designWeek.png` - weekly comparison bar charts

These are gitignored (`.gitignore` has a blanket `*.png`), so they exist only on the owner's machine. A fresh clone will not have them. Ask rather than assume they're readable.

## Views

**TARGET.** The three sections below describe the mock designs, not what `renderer.py` outputs today. Current output is much sparser: plain text header (no black bar), no badges, no delta%, no heartrate, no dashed avg lines.

### Activity View
- Header black bar
- Sub-header: "LETZTE AKTIVITÄT" + activity name + category badge + date
- Map (left, ~60% width) with cities, compass, scale, START/ZIEL markers with timestamps
- Stats column (right, ~40%): DISTANZ, HÖHE, ZEIT, Ø SPEED
- Sub-stats row: Ø PULS, MAX PULS, KALORIEN, KUDOS
- Full-width elevation profile at bottom with dual-line altitude + heartrate

Currently built: plain-text title + date, kudos badge top-right, map with cities/compass/scale (no START/ZIEL markers), 4 stats stacked right, filled altitude-only elevation profile. `activity_streams()` fetches only `altitude` + `distance`, so heartrate needs a stream-key change.

### Overview View
- Header black bar
- Two side-by-side panels (2 most-recent categories):
  - Category badge + "X / Y TRACKS" (filtered / total)
  - Map with tracks, cities, compass, scale, dates on some tracks
  - Below map: "KARTE · X / Y TRACKS · date range · km · hm" summary
  - "JAHR 2026 · <CATEGORY>" heading
  - 3 stats: DISTANZ, HÖHE, ZEIT
- Bottom row:
  - "LETZTE AKTIVITÄT" + activity summary
  - "JAHR 2026 · ALLE SPORTARTEN" total: km, hm, hours, count

Currently built: plain-text "YEAR · NAME" header, 2 panels with uppercase category label + overlaid tracks + 4 plain stat lines, single-line last-activity footer. No all-sports total.

### Weekly View
- Header black bar
- Left main area: 2 stacked bar charts (KW 29-34 or whatever last 6 weeks)
  - Top: DISTANZ KM per week, dashed avg line, current week hollow
  - Bottom: HÖHENMETER HM per week, dashed avg line, current week hollow
- Right sidebar: current week detail
  - KW number + "LÄUFT"
  - DISTANZ + delta%
  - HÖHE + delta%
  - Ø PULS + delta bpm
  - Date range MO-SO
  - Activity count + days remaining

Not built at all. Endpoint returns a centered "WEEKLY VIEW - COMING SOON" placeholder. Needs a new aggregator function for per-ISO-week buckets.

### Error View

Built and matching the design. Windows XP homage: black title bar, [X] icon, big X warning icon, configurable heading + message + optional technical details, bottom status line pointing at "Systemadministrator (Malte)". Random message variant per category from `error_messages.py`.

## Rules

**Pi shutdown:** Always `sudo shutdown -h now`, wait for green LED off. Never yank power. SD corruption learned the hard way.

**Communication style with owner:** Extremely concise, no fluff. Small numbered actionable steps. Prefix commands with `[server]` or `[pi]` or `[wsl]`. No em-dashes. Explain "why" with technical depth (owner has SE background). Never say "it works" as proof of correctness.
