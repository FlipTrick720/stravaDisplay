# Strava Display - Context for Claude Code

## Project

E-paper display showing Strava stats. Gift for a friend. Owner: Malte Braig (Master's SE, Uni Innsbruck, ADHD - prefers concise responses).

## Architecture

**Two components:**

1. **`server/`** - FastAPI app that fetches Strava data and renders PNG views
   - Runs on Render.com (Docker deployment)
   - Domain: `strava.<mydomain>.tld` (CNAME from Spaceship DNS)
   - Serves per-view PNG endpoints (see Endpoints below)
   - Holds Strava OAuth tokens in mounted config volume

2. **`pi/`** - Minimal Python client on Raspberry Pi Zero WH
   - Fetches PNGs from server, pushes to Waveshare 7.5" e-Paper HAT V2
   - Rotates through 3 view URLs, 5 min per view
   - ~40 lines total, no Strava/render code
   - systemd service for auto-start

## Endpoints

GET /display/weekly.png - week vs previous weeks bar chart view
GET /display/overview.png - year overview, 2 most-recently-used categories
GET /display/activity.png - detail of most recent activity
GET /display/error.png?category=<cat> - error screen (categories: network, auth, overload, no_activities, rate_limit, generic)
GET /health - health check for Render

Server-side caches responses for ~5 min to reduce Strava API load.

## Rendering Approach

**Component-based**, not monolithic per-view rendering. Shared components:
- `header` - black bar with year + name + timestamp + STRAVA badge
- `stat_block` - big number, unit subscript, small label, optional delta%
- `map_view` - projected tracks, cities, compass, scale bar
- `bar_chart` - weekly comparison with avg line
- `badge` - category badge (MTB, SKI, etc.)
- `elevation` - dual line chart (altitude + heartrate)

All rendering is 1-bit black/white PIL (`Image.new("1", (800, 480), 1)`) - native for Waveshare 7.5" V2.

## Sport Categorization

Extended from original 4 to cover all Strava activity types:

```python
Cycling: Ride, MountainBikeRide, GravelRide, VirtualRide, EBikeRide, EMountainBikeRide
Running: Run, TrailRun, VirtualRun
Ski:     AlpineSki, BackcountrySki, NordicSki, TourSki, Snowboard
Hiking:  Hike, Walk
Water:   Kayaking, StandUpPaddling, Surfing, Swim
Fitness: WeightTraining, Workout, Yoga, HIIT
Winter:  IceSkate, RollerSki
```

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
- Fonts: DejaVu Sans / DejaVu Sans Bold (`/usr/share/fonts/truetype/dejavu/`)

## Design Mocks

See `docs/mocks/` for reference designs:
- `activity.png` - single activity detail
- `overview.png` - year overview with 2 category panels
- `weekly.png` - weekly comparison bar charts

## Views

### Activity View
- Header black bar
- Sub-header: "LETZTE AKTIVITÄT" + activity name + category badge + date
- Map (left, ~60% width) with cities, compass, scale, START/ZIEL markers with timestamps
- Stats column (right, ~40%): DISTANZ, HÖHE, ZEIT, Ø SPEED
- Sub-stats row: Ø PULS, MAX PULS, KALORIEN, KUDOS
- Full-width elevation profile at bottom with dual-line altitude + heartrate

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

### Error View
- Windows XP homage: black title bar, [X] icon, big X warning icon
- Configurable heading + message + optional technical details
- Bottom status: "kontaktiere Administrator Malte"
- Random message variant per category

## Rules

**Pi shutdown:** Always `sudo shutdown -h now`, wait for green LED off. Never yank power. SD corruption learned the hard way.

**Communication style with owner:** Extremely concise, no fluff. Small numbered actionable steps. Prefix commands with `[server]` or `[pi]` or `[wsl]`. No em-dashes. Explain "why" with technical depth (owner has SE background). Never say "it works" as proof of correctness.
