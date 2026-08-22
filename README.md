# Strava Display

E-paper dashboard showing Strava stats. A server renders 800x480 1-bit PNGs, a
Raspberry Pi fetches them over HTTP and pushes them to the panel. The Pi renders
nothing.

## Layout

```
server/   FastAPI app. Strava fetching, aggregation, PNG rendering.
pi/       Client for the Waveshare panel.
docs/     DEPLOYMENT.md
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
```

The display endpoints never return 5xx. On failure they render an error screen,
so check the image, not the status code.

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
Production sets it to the mounted volume.

## Deployment

Self-hosted with `docker compose`, published through a Cloudflare Tunnel. No
inbound ports, no port forwarding.

```bash
cp .env.example .env     # paste Cloudflare tunnel token
docker compose up -d --build
```

Full steps: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Status

- **Phase 1 (done)** server, endpoints, Docker, compose + Cloudflare Tunnel. Not deployed yet.
- **Phase 2** real weekly view, component refactor of `renderer.py`, extended sport categories, response caching.
- **Phase 3** rewrite `pi/display.py` as a thin fetch-and-push client, systemd unit, Pi provisioning.

`pi/display.py` is the pre-server main loop, moved verbatim. It still does its
own Strava fetching and rendering and does not run as-is. Phase 3 replaces it.

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
