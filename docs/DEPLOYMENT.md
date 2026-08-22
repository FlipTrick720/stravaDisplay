# Deployment (self-hosted + Cloudflare Tunnel)

Two containers on your own box. `server` runs uvicorn, `cloudflared` dials out to
Cloudflare and serves `strava.<domain>` from it. Nothing is published to the host
and no inbound port is opened, so no port forwarding and no firewall changes.

All commands run from the repo root on the host machine.

## Prerequisites

```bash
docker --version
docker compose version
```

If missing:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out and back in
```

Also needed:

- Cloudflare account, free tier is enough
- Your domain already using Cloudflare nameservers (Cloudflare dashboard shows the zone as **Active**)

## 1. Create the tunnel

Cloudflare Zero Trust dashboard:

1. **Networks -> Tunnels -> Create a tunnel**
2. Connector type: **Cloudflared**
3. Name it, e.g. `strava-display`
4. **Save tunnel**
5. On the install screen, copy the token: the long string after `--token` in the shown command. Do not copy the whole command.

Leave the dashboard open, step 2 continues there.

## 2. Public hostname

Same tunnel, **Public Hostname** tab -> **Add a public hostname**:

| Field | Value |
|---|---|
| Subdomain | `strava` |
| Domain | `<domain>.tld` |
| Type | `HTTP` |
| URL | `server:8000` |

`server:8000` is the compose service name, resolved on the shared `internal`
network. It is not a hostname that exists on your LAN.

Save. Cloudflare creates the DNS record itself, nothing to add at the registrar.

## 3. Token

```bash
cp .env.example .env
$EDITOR .env          # paste the token into TUNNEL_TOKEN
```

Confirm it substituted:

```bash
docker compose config | grep TUNNEL_TOKEN
```

Must show the real token, not blank.

## 4. Bootstrap Strava config

`setup_strava.py` is interactive (paste an OAuth code), so run it locally, then
move the result onto the data volume.

```bash
cd server && python3 setup_strava.py && cd ..
mv config.json data/config.json
ls -la data/
```

`data/config.json` is gitignored. Token refresh rewrites it roughly every 6h, so
back it up if you care about not redoing OAuth.

## 5. Start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Expect cloudflared to log `Registered tunnel connection`. The dashboard shows the
tunnel as **Healthy**.

## 6. Verify

```bash
curl -s https://strava.<domain>.tld/health

curl -s -o act.png  -w "%{http_code} %{content_type} %{size_download}\n" https://strava.<domain>.tld/display/activity.png
curl -s -o ovw.png  -w "%{http_code} %{content_type} %{size_download}\n" https://strava.<domain>.tld/display/overview.png
curl -s -o week.png -w "%{http_code} %{content_type} %{size_download}\n" https://strava.<domain>.tld/display/weekly.png

file act.png   # PNG image data, 800 x 480, 1-bit grayscale
```

Display endpoints never return 5xx. On failure they render the XP error screen,
so open the image, do not trust the status code. The technical details line shows
where config resolution landed:

- `config.json not found at /data/config.json` -> volume mounted, not seeded. Redo step 4.
- `config.json not found at /app/config.json` -> `STRAVA_CONFIG_DIR` did not apply. Check `docker-compose.yml`.
- Real data, no error screen -> done.

Force an error screen deliberately to sanity check rendering:

```bash
curl -s -o err.png https://strava.<domain>.tld/display/error.png?category=network
```

`weekly.png` is a placeholder until Phase 2.

## Update

```bash
git pull
docker compose up -d --build
```

`./data` is a host directory, untouched by rebuilds. Tokens survive.

## Rollback

```bash
git log --oneline -10
git checkout <sha>
docker compose up -d --build
```

Back to current:

```bash
git checkout main
docker compose up -d --build
```

## Operations

```bash
docker compose logs -f server        # app logs
docker compose logs -f cloudflared   # tunnel logs
docker compose restart server
docker compose down                  # stop both, keeps ./data
docker compose up -d --build         # after any code or Dockerfile change
```

Debug from inside the network without exposing a port:

```bash
docker compose exec server curl -s localhost:8000/health
docker compose exec server ls -la /data
```

## Notes

**No published ports.** `server` has `expose`, not `ports`, so it is unreachable
from the LAN and from the internet except through the tunnel. Adding a `ports:`
entry to reach it locally undoes that; prefer `docker compose exec` above.

**Network name is cosmetic.** The network is called `internal`, but do not add
`internal: true` to it. That flag blocks egress and cloudflared would never reach
Cloudflare.

**cloudflared waits for health.** `depends_on` uses `condition: service_healthy`
against the `/health` endpoint, so the tunnel does not advertise a dead origin
during a slow start.

**Auth is Cloudflare's job.** The tunnel publishes these endpoints to the open
internet with no auth. Anyone with the URL can read your Strava stats. To lock it
down, put a Zero Trust Access policy on the hostname, but note the Pi client
would then need a service token.

**Host uptime.** Unlike a PaaS, this is only up while your box is. `restart:
unless-stopped` covers reboots once Docker starts on boot.
