# Strava Display

E-paper dashboard showing Strava stats. A server renders 800x480 1-bit PNGs and
a Raspberry Pi fetches them over HTTP and pushes them to a Waveshare 7.5" panel.

**Live:** https://strava-display.maltebraig.com

## Docs

| | |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagram, request flow, where secrets live |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Setup from scratch, redeploy, rollback |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Logs, restarts, failure modes |
| [pi/setup.md](pi/setup.md) | Pi-side install, systemd service, troubleshooting |
| [CLAUDE.md](CLAUDE.md) | Full project context, design language, phase status |

## Layout

```
server/   FastAPI app. Strava fetching, aggregation, PNG rendering.
          Dockerfile lives here; build context is the repo root.
pi/       Slim fetch-and-push client for the Waveshare panel. See pi/setup.md.
docs/     Architecture, deployment, operations.
data/     Bind-mounted to /data. Holds config.json in production.
tests/    pytest
setup/    Pi provisioning scripts
```

## Endpoints

```
GET /display/activity.png    most recent activity
GET /display/overview.png    year overview, 2 most-recent categories
GET /display/weekly.png      placeholder until Phase 2
GET /display/error.png?category=network
GET /health
GET  /admin/cache        cache freshness JSON      (bearer auth)
POST /admin/bootstrap    upload config.json        (bearer auth)
```

Views are pre-rendered by a background task every 4 minutes and served from an
in-memory cache, so requests never hit the Strava API. Each response carries
`X-Generated-At`.

Display endpoints never return 5xx. On failure they render an error screen as a
200 PNG, so check the image, not the status code.

## Local development

```bash
pip install -r requirements.txt

# cwd matters: app.py imports its siblings as top-level modules
cd server && python3 -m uvicorn app:app --reload --port 8000
```

Then open `http://localhost:8000/display/overview.png`.

Render previews without a server:

```bash
cd server
python3 renderer.py                # overview
python3 renderer.py latest         # single activity
python3 renderer.py error network  # error screen
```

Tests:

```bash
python3 tests/test_aggregator.py   # or: pytest tests/
```

## Strava OAuth

Register an app at https://www.strava.com/settings/api (name must not contain
"Strava", callback domain `localhost`). Then:

```bash
cp config.example.json config.json   # fill in client_id + client_secret
cd server && python3 setup_strava.py
```

Writes tokens into `config.json`. Gitignored, never commit it.

`config.json` is read from `$STRAVA_CONFIG_DIR` if set, otherwise the repo root.
Production sets it to `/data`.

## Deployment

Self-hosted on Ubuntu with `docker compose`, published through a Cloudflare
Tunnel. No inbound ports, no port forwarding.

```bash
cp .env.example .env     # TUNNEL_TOKEN + STRAVA_ADMIN_TOKEN
docker compose up -d --build
```

The server refuses to start without `STRAVA_ADMIN_TOKEN`; generate one with
`openssl rand -hex 32`.

Full steps: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Status

- **Phase 1 (done, deployed)** server, endpoints, Docker Compose, Cloudflare Tunnel. Live and verified end-to-end.
- **Done since** server-side caching with background refresh, `/admin/bootstrap` remote config upload, slim Pi client.
- **Phase 2** weekly view, redesign existing views to the new mocks.

## Hardware

- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800x480)
- microSD, 5V/2.5A supply

Case dimensions for 3D print:

- Display active area: 170.2 x 111.2 mm
- Full panel: 178.85 x 121.98 x 1.18 mm
- Driver HAT: 65 x 30.2 x 15 mm

## Rules

**Never yank power on the Pi.** Always:

```bash
sudo shutdown -h now
```

Wait until the green LED is off. Otherwise SD corruption.
