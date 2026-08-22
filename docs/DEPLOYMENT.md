# Deployment

Live at **https://strava-display.maltebraig.com**

| | |
|---|---|
| Host | Ubuntu Server, self-hosted, SSH access |
| Runtime | Docker Compose, 2 containers (`server`, `cloudflared`) |
| Ingress | Cloudflare Tunnel. No inbound port, no port forwarding |
| Repo path | `~/stravaDisplay` |
| Secrets | `.env` (tunnel token), `data/config.json` (Strava tokens) |

Day-2 tasks (logs, restarts, failure modes) are in
[OPERATIONS.md](OPERATIONS.md). System design is in
[ARCHITECTURE.md](ARCHITECTURE.md).

All commands run from `~/stravaDisplay` on the server unless marked `[local]`.

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

Plus a Cloudflare account with the domain on Cloudflare nameservers (zone shows
**Active** in the dashboard).

### Generate the admin token

`/admin/bootstrap` and `/admin/cache` are guarded by a bearer token. **The
server refuses to start if `STRAVA_ADMIN_TOKEN` is unset**, so this is a
prerequisite, not an optional extra.

```bash
openssl rand -hex 32
```

Keep the output; it goes into `.env` in step 4 and into your `curl` calls.

> **Upgrading an existing deployment:** a `git pull` that brings in the admin
> endpoints will fail to start until `STRAVA_ADMIN_TOKEN` is present in `.env`.
> Add it before `docker compose up -d --build`.

## First-time setup

These are the steps that produced the current deployment. Follow them to
rebuild from scratch on a new host.

### 1. Create the tunnel

Cloudflare Zero Trust dashboard:

1. **Networks -> Tunnels -> Create a tunnel**
2. Connector type: **Cloudflared**
3. Name: `strava-display`
4. **Save tunnel**
5. On the install screen, copy the token: the long string after `--token`. Not the whole command.

### 2. Public hostname

Same tunnel, **Public Hostname** tab -> **Add a public hostname**:

| Field | Value |
|---|---|
| Subdomain | `strava-display` |
| Domain | `maltebraig.com` |
| Type | `HTTP` |
| URL | `server:8000` |

`server:8000` is the compose service name on the `internal` network, not a LAN
hostname. Cloudflare creates the DNS record itself, nothing to add at the
registrar.

### 3. Clone

```bash
ssh <user>@<server>
git clone https://github.com/FlipTrick720/stravaDisplay.git ~/stravaDisplay
cd ~/stravaDisplay
```

### 4. Tunnel token

```bash
cp .env.example .env
nano .env          # TUNNEL_TOKEN and STRAVA_ADMIN_TOKEN
```

Confirm both substituted:

```bash
docker compose config | grep -E "TUNNEL_TOKEN|STRAVA_ADMIN_TOKEN"
```

Must show real values, not blanks. A blank `STRAVA_ADMIN_TOKEN` means the
container exits at startup.

### 5. Start

```bash
docker compose up -d --build
docker compose ps
```

Both services should be `running`, `server` should be `healthy`. Until step 6
the display endpoints serve the error screen; that is expected.

### 6. Bootstrap Strava config

`setup_strava.py` is interactive (paste an OAuth code in a browser round trip),
so run it on your workstation, then upload the result over the tunnel.

```bash
[local] cd server && python3 setup_strava.py && cd ..
[local] curl -X POST \
             -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \
             -F "config=@config.json" \
             https://strava-display.maltebraig.com/admin/bootstrap
```

```json
{"status":"ok","next_refresh":"immediate"}
```

The endpoint validates the file, writes it atomically to `/data/config.json`,
and kicks off an immediate re-render instead of waiting for the next 4-minute
tick. No SSH needed.

`scp` still works if you prefer it:

```bash
[local] scp config.json <user>@<server>:~/stravaDisplay/data/config.json
docker compose restart server
```

`data/config.json` is gitignored and survives rebuilds. Token refresh rewrites
it roughly every 6h.

## Verify

```bash
curl -s https://strava-display.maltebraig.com/health
# {"status":"ok"}

curl -s -o act.png  -w "%{http_code} %{content_type} %{size_download}\n" https://strava-display.maltebraig.com/display/activity.png
curl -s -o ovw.png  -w "%{http_code} %{content_type} %{size_download}\n" https://strava-display.maltebraig.com/display/overview.png

file act.png   # PNG image data, 800 x 480, 1-bit grayscale
```

In a browser, open
`https://strava-display.maltebraig.com/display/overview.png`. It should render
real activity data, not the error screen.

Display endpoints never return 5xx. On failure they return the error screen as a
200 PNG, so **look at the image**, do not trust the status code. The technical
details line names the cause:

- `config.json not found at /data/config.json` -> mount is live, file missing. Redo step 5.
- `config.json not found at /app/config.json` -> `STRAVA_CONFIG_DIR` did not apply. Check `docker-compose.yml`.

`weekly.png` is a placeholder until Phase 2.

## Update

```bash
cd ~/stravaDisplay
git pull
docker compose up -d --build
```

`./data` is a host directory, untouched by rebuilds. Tokens survive.

## Logs

```bash
docker compose logs -f              # both services
docker compose logs -f server       # app
docker compose logs -f cloudflared  # tunnel
```

## Restart

```bash
docker compose restart server       # app only
docker compose restart cloudflared  # tunnel only
docker compose restart              # both
docker compose down && docker compose up -d   # full recreate, keeps ./data
```

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

## Notes

**No published ports.** `server` uses `expose`, not `ports`, so it is
unreachable from the LAN and the internet except through the tunnel. To poke it
directly, use `docker compose exec server curl -s localhost:8000/health` rather
than adding a `ports:` entry.

**Do not set `internal: true`** on the `internal` network. Despite the name that
flag blocks egress, and cloudflared would never reach Cloudflare.

**No auth.** The tunnel publishes these endpoints to the open internet. Anyone
with the URL can read the Strava stats. A Zero Trust Access policy would fix it,
but the Pi client would then need a service token.

**Uptime is the host's.** `restart: unless-stopped` covers reboots provided
Docker starts on boot (`sudo systemctl enable docker`).
