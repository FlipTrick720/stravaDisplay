# Strava Display - Context for Claude Code

## Project

E-paper display showing Strava stats. Gift for a friend. Owner: Malte Braig (Master's SE, Uni Innsbruck, ADHD - prefers concise responses).

## Status

**Phase 1 COMPLETE and deployed.** Live at `strava-display.maltebraig.com`, self-hosted on an Ubuntu server (SSH), Docker Compose, Cloudflare Tunnel. Verified end-to-end through the tunnel: `/health`, `/display/overview.png`, `/display/activity.png`, `/display/error.png`. `/display/weekly.png` returns a placeholder.

**Phase 2 scope:**
1. Weekly view (real implementation, replacing the placeholder)
2. Redesign the existing views to match the new mocks
3. ~~Rewrite `pi/display.py` as the slim fetch-and-push client~~ **DONE**

Also done ahead of schedule: server-side caching with background refresh, and the `/admin/bootstrap` remote config upload.

Carried over, not currently scheduled: component refactor of `renderer.py`, extended sport categories. See the TARGET sections below; they are still accurate descriptions of unbuilt work.

Sections below marked **TARGET** describe the intended end state and are NOT implemented yet. Do not assume that code exists.

## Architecture

**Two components:**

1. **`server/`** - FastAPI app that fetches Strava data and renders PNG views
   - Self-hosted via docker-compose, exposed through a Cloudflare Tunnel
   - Domain: `strava.<mydomain>.tld`, DNS managed by Cloudflare (domain must be on Cloudflare nameservers)
   - Serves per-view PNG endpoints (see Endpoints below)
   - Holds Strava OAuth tokens in `./data` on the host, bind-mounted to `/data` in the container

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
server/Dockerfile   python:3.11-slim, uvicorn on :8000. Build context is REPO ROOT
docker-compose.yml  server + cloudflared, shared `internal` network, no published ports
.dockerignore       keeps data/, .env, .git out of the build context
.env.example        TUNNEL_TOKEN documentation. Copy to .env (gitignored)
docs/ARCHITECTURE.md  system diagram, request flow, where secrets live
docs/DEPLOYMENT.md    setup + redeploy runbook
docs/OPERATIONS.md    logs, restarts, failure modes
data/               host bind mount -> /data. Holds config.json in prod. .gitkeep tracked
config.json         secrets, gitignored. Repo root for local dev; data/ in prod
```

## Endpoints

GET /display/weekly.png - week vs previous weeks bar chart view (**placeholder**, renders "COMING SOON")
GET /display/overview.png - year overview, 2 most-recently-used categories
GET /display/activity.png - detail of most recent activity
GET /display/error.png?category=<cat> - error screen (categories: network, auth, overload, no_activities, rate_limit, generic)
GET /health - health check, used by the compose healthcheck
GET /admin/cache - cache freshness JSON (bearer auth)
POST /admin/bootstrap - upload config.json (bearer auth, multipart field "config")

`overview.png` and `activity.png` never return 5xx. On any fetch/render failure they fall back to `renderer.render_error()` with the exception mapped to a category, so the Pi always gets a displayable 800x480 PNG. Mapping lives in `app.py:_render_error_for_exception` and duplicates the logic from the old `display.py`; keep the two in sync or unify them in Phase 2.

**Caching is implemented.** A background task (`_refresh_loop` in `app.py`) re-renders every view every 240s into an in-memory dict; handlers only return cached bytes. Requests never hit Strava. A failed render keeps the previous bytes rather than replacing them with an error, except on a cold cache. Every PNG response carries `X-Generated-At`.

`/admin/*` is guarded by `STRAVA_ADMIN_TOKEN`; the server **refuses to start** if it is unset.

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
- **Prod:** `STRAVA_CONFIG_DIR=/data` (set in `docker-compose.yml`), pointing at the bind mount. Host side is `./data`.

Resolved at import, so the env var must be set before `config` is imported. Fine via compose `environment:`, but relevant if anything ever sets it at runtime.

This is what decouples the token store from the image. The mount must not land on `/app`, which would shadow the deployed code.

## Deployment (Cloudflare Tunnel)

**Deployed and live.** The only deployment target.

| | |
|---|---|
| Domain | `strava-display.maltebraig.com` |
| Host | Ubuntu Server, self-hosted, reached over SSH |
| Repo path | `~/stravaDisplay` |
| Runtime | Docker Compose, 2 containers |
| Ingress | Cloudflare Tunnel, no inbound port |

Docs: `docs/DEPLOYMENT.md` (setup and redeploy), `docs/OPERATIONS.md` (logs, restarts, failure modes), `docs/ARCHITECTURE.md` (diagram, request flow, secrets).

### Known limitations

Accepted for now. Do not treat any of these as bugs to fix mid-task without asking.

- **No monitoring or alerting.** Nothing notices if it goes down; you find out from a stale panel.
- **No backups of `data/config.json`.** It is the only unrecoverable state. A lost disk means redoing the OAuth flow.
- **No CI/CD.** Deploys are a manual `git pull` + `docker compose up -d --build` over SSH.
- **refresh_token rotation is untested.** Strava may rotate the refresh token; the atomic write path exists but has not been exercised through a real rotation.
- **No auth on the endpoints.** The tunnel publishes them to the open internet.
- **Admin token is a single shared secret.** No rotation, no per-client tokens. Leaking it allows overwriting the Strava config.
- **Cache is in-memory only.** A container restart drops it back to the loading placeholder until the first background round completes (a few seconds).

Two containers via `docker compose`:
- `server` - builds from `server/Dockerfile`, `STRAVA_CONFIG_DIR=/data`, bind mount `./data:/data`
- `cloudflared` - `cloudflare/cloudflared:latest`, `tunnel --no-autoupdate run`, `TUNNEL_TOKEN` from `.env`

Docker mirrors the dev server: `WORKDIR /app/server` so `app.py` can import its siblings as top-level modules. That WORKDIR does not determine where `config.json` is found; `STRAVA_CONFIG_DIR` does.

**Build context is the repo root even though the Dockerfile lives in `server/`.** It COPYs `requirements.txt` and `config.example.json`, both of which sit at the root, so compose sets `context: .` with `dockerfile: server/Dockerfile`. Changing the context to `./server` breaks those COPYs. `.dockerignore` keeps `data/`, `.env` and `.git/` out of the context.

**No published ports.** `server` uses `expose`, not `ports`. Nothing is bound on the host and no inbound firewall rule exists; the tunnel dials out. Adding a `ports:` entry undoes that. Use `docker compose exec server curl -s localhost:8000/health` to poke it instead.

**Routing:** the Cloudflare dashboard maps `strava.<domain>` to `http://server:8000`, resolved by compose DNS on the shared `internal` network. Cloudflare creates the DNS record itself, nothing at the registrar.

**Network naming trap:** the network is named `internal`, but never set `internal: true` on it. That flag blocks egress and cloudflared could not reach Cloudflare's edge.

**Not yet done:** never deployed, `./data` has no `config.json`. Until bootstrapped, the Strava endpoints return the XP error screen (not a 5xx) with "config.json not found at /data/config.json" in the technical details. That message is the quickest check that the mount is live but unseeded; `/app/config.json` instead would mean `STRAVA_CONFIG_DIR` did not apply.

**Bootstrap:** `setup_strava.py` is interactive (paste an OAuth code), so run it locally and `mv config.json data/config.json`. Token refresh rewrites that file roughly every 6h via atomic write, so `./data` must persist across rebuilds. It does, being a host directory.

**No auth.** The tunnel publishes these endpoints to the open internet. Anyone with the URL reads the Strava stats. A Zero Trust Access policy would fix it but the Pi client would then need a service token.

**Uptime is the host's.** Only reachable while the box is up. `restart: unless-stopped` covers reboots if Docker starts on boot.

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
