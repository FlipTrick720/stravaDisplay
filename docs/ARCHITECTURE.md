# Architecture

Deployed state as of Phase 1. The server renders, the Pi displays, Cloudflare
carries traffic without any inbound port being opened.

## System

```
  +---------------------------+
  |  Raspberry Pi Zero WH     |
  |  Waveshare 7.5" V2        |
  |  pi/display.py            |   rotates 3 view URLs, 5 min each
  +-------------+-------------+
                |
                |  HTTPS GET https://strava-display.maltebraig.com/display/overview.png
                v
  +---------------------------+
  |  Cloudflare Edge          |   DNS, TLS termination, DDoS
  +-------------+-------------+
                |
                |  tunnel, carried over a connection cloudflared
                |  opened OUTBOUND. No inbound port, no port forward.
                v
==================================================================
  Ubuntu Server (self-hosted, SSH access)
  ~/stravaDisplay, docker compose

  +--------------------------------------------------------------+
  |  docker network "internal" (bridge)                           |
  |                                                               |
  |   +------------------+          +-------------------------+   |
  |   |  cloudflared     |  HTTP    |  server                 |   |
  |   |  tunnel run      |--------->|  uvicorn :8000          |   |
  |   |                  |          |  FastAPI (app.py)       |   |
  |   +--------+---------+          +-----------+-------------+   |
  |            ^                                |                 |
  |            | TUNNEL_TOKEN                   | reads/writes    |
  |            | (from .env)                    v                 |
  |            |                        /data/config.json         |
  |            |                     (bind mount ./data)          |
  +------------|--------------------------------|-----------------+
               |                                 |
==================================================================
                                                 |  HTTPS
                                                 v
                                    +-------------------------+
                                    |  Strava API v3          |
                                    +-------------------------+
```

Neither container publishes a host port. `server` uses `expose`, so it is
reachable only from inside the `internal` network. The single route in from the
internet is the tunnel.

## Components

| Component | Responsibility |
|---|---|
| `pi/display.py` | Fetch PNG over HTTP, push bytes to the panel. No Strava calls, no rendering. **Not yet rewritten**, see Status. |
| Cloudflare Edge | Public DNS for `strava-display.maltebraig.com`, TLS, routes to the tunnel |
| `cloudflared` container | Holds the outbound tunnel connection, forwards requests to `server:8000` |
| `server` container | uvicorn + FastAPI. All Strava fetching, aggregation, PNG rendering |
| `server/app.py` | Endpoint routing, exception to error-screen mapping |
| `server/strava_client.py` | Thin `requests` wrapper. Token refresh at init, one retry on 401 |
| `server/aggregator.py` | Categorizes activities, picks 2 most-recent categories, YTD totals |
| `server/renderer.py` | PIL 1-bit 800x480 rendering for all views |
| `server/config.py` | Loads/saves `config.json`, atomic write on save |
| `./data` (host dir) | Persists `config.json` across container rebuilds |

## Request flow

What happens when the Pi requests `/display/overview.png`:

1. Pi issues `GET https://strava-display.maltebraig.com/display/overview.png`.
2. Cloudflare edge resolves the hostname, terminates TLS, matches the public
   hostname rule for this tunnel.
3. Edge hands the request down the tunnel to `cloudflared` on the server.
4. `cloudflared` forwards it to `http://server:8000/display/overview.png`,
   resolving `server` via docker DNS on the `internal` network.
5. uvicorn routes to `overview_png()` in `app.py`, which returns the cached
   bytes for `overview` plus an `X-Generated-At` header. No Strava call, no
   rendering. This is the whole request path.
6. Response travels back through the tunnel to the Pi, which pushes it to the
   panel and logs the `X-Generated-At` value.

The rendering happens out of band, every 240s:

1. `_refresh_loop()` calls `refresh_all()`.
2. Each render runs via `asyncio.to_thread`, since PIL and `requests` are
   blocking and would otherwise stall the event loop.
3. `StravaClient()` is constructed: `config.load()` reads `/data/config.json`.
   If the access token expires within 60s, it refreshes and `config.save()`
   atomically rewrites `/data/config.json`.
4. `activities_since(year_start)` pages the year's activities. `athlete()`
   fetches the display name.
5. `aggregator.build_overview()` sorts newest-first, picks the 2 most-recently
   used categories, sums YTD distance/elevation/time, filters polylines to the
   dominant geographic cluster.
6. `renderer.render_overview()` draws a 1-bit 800x480 PIL image, encoded to PNG
   and stored in the cache.

If a render raises, the previous cached bytes stay in place and the failure is
logged. On a cold cache, `_render_error_for_exception()` maps the exception to a
category and the error screen is cached instead. Display endpoints never return
5xx, because the Pi has no way to show an HTTP error.

### Strava API cost

Requests do **not** hit Strava. A background task re-renders every view every
240s into an in-memory cache; handlers only hand back bytes. Strava traffic is
therefore constant no matter how often the Pi polls.

Per background round:

| View | Strava calls |
|---|---|
| `overview` | 1 paginated activities call (+1 per extra 100 activities) + 1 athlete call |
| `activity` | 3 (list, activity detail, streams) |
| `weekly` | 0 (placeholder) |
| all 6 error categories | 0 |

Roughly 5 calls per round, 15 rounds an hour, plus a token refresh POST every
~6h. Well inside Strava's rate limits, and adding Pi clients or shortening the
poll interval costs nothing extra.

### Cache behaviour

- **Startup** seeds a "LADE DATEN..." placeholder so traffic is served
  instantly. Blocking startup on Strava would trip the compose healthcheck and
  delay cloudflared, so the first real round runs in the background.
- **A failed render never overwrites a good entry.** A stale panel beats an
  error panel. The exception is a cold cache or a placeholder still in place,
  where the error screen is more useful than an indefinite "loading".
- **`X-Generated-At`** on every PNG response carries the render timestamp. The
  Pi logs it, so a stuck cache is visible from the Pi's journal.
- **`GET /admin/cache`** reports `age_seconds` and `size_bytes` per view.

## Secrets

| Secret | Lives in | Reaches the app via |
|---|---|---|
| Cloudflare tunnel token | `.env` at repo root, gitignored | `TUNNEL_TOKEN` env var on the `cloudflared` container |
| Strava client id/secret, access + refresh tokens | `data/config.json`, gitignored | bind mount `./data:/data`, read by `config.py` via `STRAVA_CONFIG_DIR=/data` |

Neither is baked into the image. `.dockerignore` excludes `.env` and `data/`
from the build context, so they are not even sent to the Docker daemon.

`data/config.json` is rewritten in place on every token refresh. It is the only
piece of state that cannot be recreated from the repo, and there is no backup.
Losing it means re-running the OAuth flow.

## Status

Working through the deployed pipe: `/health`, `/display/overview.png`,
`/display/activity.png`, `/display/error.png`.

`/display/weekly.png` returns a placeholder image until Phase 2.

`pi/display.py` is still the pre-server main loop, moved verbatim from the old
`src/`. It does its own Strava fetching and rendering and does not run as-is.
The Pi leg of the diagram above is the intended design, not the current code.
