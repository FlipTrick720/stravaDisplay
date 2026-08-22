# Operations

Day-2 playbook for the running deployment. Setup is in
[DEPLOYMENT.md](DEPLOYMENT.md), design is in [ARCHITECTURE.md](ARCHITECTURE.md).

All commands run from `~/stravaDisplay` on the Ubuntu server.

## Quick status

```bash
docker compose ps
curl -s https://strava-display.maltebraig.com/health
```

Healthy looks like: both services `running`, `server` marked `healthy`, and
`{"status":"ok"}` from the health endpoint.

## Logs

```bash
docker compose logs -f                    # both, follow
docker compose logs -f server             # app only
docker compose logs -f cloudflared        # tunnel only
docker compose logs --tail 100 server     # last 100 lines
docker compose logs --since 30m server    # last 30 minutes
```

Every request logs an access line:

```
INFO:  172.18.0.3:52134 - "GET /display/overview.png HTTP/1.1" 200 OK
```

A 200 does **not** mean success. Display endpoints return the error screen as a
200 PNG. Confirm by opening the image.

## Restart

```bash
docker compose restart server        # app only, fastest
docker compose restart cloudflared   # tunnel only
docker compose restart               # both
docker compose down && docker compose up -d    # full recreate
```

`docker compose down` does not touch `./data`. Tokens survive.

## Rebuild after a code change

```bash
git pull
docker compose up -d --build
```

Only `server` rebuilds; `cloudflared` is a pulled image. Needed after any change
to `server/`, `requirements.txt`, or `server/Dockerfile`. Not needed for
`docs/` or `README.md`.

## Check the tunnel

```bash
docker compose logs cloudflared | tail -30
```

Connected looks like this, usually four connections to different Cloudflare
colos:

```
INF Registered tunnel connection connIndex=0 location=fra01
INF Registered tunnel connection connIndex=1 location=muc01
INF Registered tunnel connection connIndex=2 location=fra01
INF Registered tunnel connection connIndex=3 location=muc01
```

Also visible in Zero Trust -> Networks -> Tunnels, where the tunnel should show
**Healthy**.

Broken looks like `ERR Failed to create new quic connection`, repeated
`Unauthorized` errors, or a `Retrying connection in ...` loop.

## Check the app

```bash
curl -s https://strava-display.maltebraig.com/health     # through the tunnel
docker compose exec server curl -s localhost:8000/health  # bypassing the tunnel
```

Running both separates an app problem from a tunnel problem. If the inside one
works and the outside one does not, the tunnel is the fault.

## Check the cache

Views are pre-rendered every 240s; requests never hit Strava. To see freshness:

```bash
curl -s -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \
     https://strava-display.maltebraig.com/admin/cache | python3 -m json.tool
```

```json
{"overview": {"age_seconds": 42.1, "size_bytes": 3368, "placeholder": false}}
```

- `age_seconds` climbing past ~300 means the refresh loop is stuck or every render is failing. Check `docker compose logs server` for `Render failed`.
- `"placeholder": true` means the first round has not succeeded yet since startup.

Every PNG response also carries the render time:

```bash
curl -sI https://strava-display.maltebraig.com/display/overview.png | grep -i x-generated-at
```

The Pi logs this on each fetch, so `journalctl -u strava-display` on the Pi
shows server-side staleness without touching the server.

## Re-upload Strava config

Replaces the scp step. Run OAuth locally, push the result over the tunnel:

```bash
[local] cd server && python3 setup_strava.py && cd ..
[local] curl -X POST \
             -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \
             -F "config=@config.json" \
             https://strava-display.maltebraig.com/admin/bootstrap
```

Validates the file, writes it atomically to `/data/config.json`, and triggers an
immediate re-render. No restart needed.

## Failure modes

### Tunnel disconnected

Symptom: the domain returns a Cloudflare 502/1033 error page, or times out.
`docker compose logs cloudflared` shows auth failures or a retry loop.

```bash
docker compose logs cloudflared | tail -30
grep TUNNEL_TOKEN .env                # present and not the placeholder?
docker compose config | grep TUNNEL_TOKEN   # actually substituted?
docker compose restart cloudflared
```

If the token is wrong or was rotated, regenerate it in the Zero Trust dashboard
(same tunnel -> Configure), put the new value in `.env`, then:

```bash
docker compose up -d cloudflared      # recreate so the new env is picked up
```

`restart` alone does not reload `.env`. `up -d` does.

### Strava 401

Symptom: endpoints return the auth error screen. `docker compose logs server`
shows a 401 from Strava, or `StravaAuthError`.

The client refreshes the access token automatically and retries a 401 once. A
persistent 401 means the **refresh token** itself is rejected, which needs a new
OAuth run:

```bash
[local] cd server && python3 setup_strava.py
[local] scp config.json <user>@<server>:~/stravaDisplay/data/config.json
docker compose restart server
```

### Strava 429 (rate limited)

Symptom: the rate-limit error screen. Requests are served from cache, so Pi
polling cannot cause this. Strava traffic comes only from the 240s background
round (~5 calls). This points at something else using the same Strava app
credentials, or many container restarts each triggering a fresh round.

```bash
docker compose logs --since 1h server | grep -c "Rendered overview"
```

Expect around 15 per hour. Far more means a restart loop.

### Container will not start

```bash
docker compose ps                # which one is not running
docker compose logs server       # the actual error
docker compose up -d --build     # rebuild if it is a stale image
docker compose config            # validate the YAML and env substitution
```

Common causes: `.env` missing so `TUNNEL_TOKEN` is blank, a syntax error from a
recent edit, or a failed build (watch the build output, not just the logs).

### Error screen but everything looks up

Fetch the image and read its technical details line, which names the cause:

```bash
curl -s -o /tmp/ovw.png https://strava-display.maltebraig.com/display/overview.png
```

- `config.json not found at /data/config.json` -> the file is missing from `./data`. Restore or re-bootstrap.
- `config.json not found at /app/config.json` -> `STRAVA_CONFIG_DIR` did not apply. Check `docker-compose.yml` and recreate with `up -d`.
- `ConnectionError` / `Timeout` -> the server cannot reach the Strava API. Check egress from the host.

### Disk full

Docker image layers accumulate across rebuilds.

```bash
df -h
docker system df
docker image prune -f        # dangling images only, safe
docker system prune -a       # everything unused. Re-pulls cloudflared next up
```

Never `docker volume prune` without checking. `./data` is a bind mount, not a
named volume, so it is unaffected, but be deliberate.

## Lost Strava tokens

`data/config.json` is the only state that cannot be rebuilt from the repo, and
**there is no backup**. If it is lost or corrupted:

```bash
[local] cd server && python3 setup_strava.py
[local] scp config.json <user>@<server>:~/stravaDisplay/data/config.json
docker compose restart server
```

`setup_strava.py` needs `client_id` and `client_secret` in a local
`config.json`; copy `config.example.json` and refill them from
https://www.strava.com/settings/api if that is gone too.

Take a backup now, before you need one:

```bash
cp data/config.json ~/config.json.bak-$(date +%F)
```

Treat the copy as a credential.

## Deliberate checks

```bash
# force an error screen, confirms rendering works independently of Strava
curl -s -o /tmp/err.png "https://strava-display.maltebraig.com/display/error.png?category=network"

# inspect the config the container actually sees
docker compose exec server ls -la /data
docker compose exec server python -c "import config; print(config.CONFIG_PATH)"
```
