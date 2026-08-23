# Bootstrapping Strava credentials

How to point the deployed server at a Strava account - your own after a
re-auth, or the gift recipient's the first time. This is the full walkthrough;
[OPERATIONS.md](OPERATIONS.md#re-upload-strava-config) has the same flow
condensed to a copy-paste block once you've done it once.

All commands run on your WSL machine unless marked `[server]`.

## Prerequisites

- The Strava account's login (username/password) you're bootstrapping.
  For the recipient: you do the OAuth authorize click on their behalf, so
  either they're on the call or they've given you the go-ahead to log in
  as them for a minute.
- Your laptop, with WSL and this repo cloned (`~/stravaDisplay` or wherever
  you keep it).
- `STRAVA_ADMIN_TOKEN` - the same value that's in `.env` on the server.
  It's in your password manager; if it's not, SSH to the server and
  `cat .env` (see [OPERATIONS.md](OPERATIONS.md)).
- The server reachable at `https://strava-display.maltebraig.com`
  (`curl https://strava-display.maltebraig.com/health` should return
  `{"status":"ok"}`).

## Flow

### a. Register a separate Strava app (optional)

Skip this if you're reusing the existing Strava API app (same `client_id`/
`client_secret` as today, just new tokens). Only do this if you specifically
want the recipient's account on its own app registration - e.g. so revoking
their access later doesn't touch yours.

1. Log into the Strava account this app should belong to.
2. https://www.strava.com/settings/api -> create an app.
   - Authorization Callback Domain: `localhost` (matches `REDIRECT_URI` in
     `setup_strava.py` - the redirect will show "connection refused" in the
     browser, that's expected, see step b).
3. Note the new `client_id` and `client_secret`.

### b. Run the OAuth flow locally

```bash
[local] cd ~/stravaDisplay/server
[local] python3 setup_strava.py
```

This is interactive:

1. It prints an authorization URL. Open it in a browser logged into the
   Strava account you're bootstrapping (the recipient's, or your own after
   re-auth).
2. Click "Authorize".
3. Strava redirects to `http://localhost/?code=XYZ&scope=...` and the
   browser shows a connection error - expected, `localhost` isn't serving
   anything. The code you need is in that URL bar.
4. Copy the `code` query parameter value, paste it back into the terminal
   prompt.
5. The script exchanges it for an access + refresh token and writes
   `server/config.json`.

If you did step a, the script will ask for `client_id`/`client_secret` too -
use the new app's values instead of the defaults.

### c. Verify config.json was created

```bash
[local] cd ~/stravaDisplay/server
[local] python3 -c "import json; c=json.load(open('config.json')); print(c['strava']['client_id'], bool(c['strava']['access_token']))"
```

Should print a client id and `True`. If `config.json` is missing, step b
didn't finish - re-run it.

### d. Upload to the server

```bash
[local] curl -X POST \
             -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \
             -F "config=@config.json" \
             https://strava-display.maltebraig.com/admin/bootstrap
```

Expect `{"status":"ok","next_refresh":"immediate"}`. A `400` means the
uploaded file failed validation (see below) - fix locally and re-upload, the
server hasn't changed anything. A `401` means `STRAVA_ADMIN_TOKEN` is wrong.

### e. Verify

```bash
[local] curl -s https://strava-display.maltebraig.com/display/activity.png -o /tmp/check.png
```

Open `/tmp/check.png` - it should show the new account's most recent
activity, not the previous account's. Give it a few seconds first; see
"What the server does" below for why. `/admin/cache` confirms freshness:

```bash
[local] curl -s -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \
             https://strava-display.maltebraig.com/admin/cache
```

`activity.generated_at` should be within the last minute or so.

## What the server does on receipt

`/admin/bootstrap` parses the upload as JSON and checks that
`strava.{client_id,client_secret,access_token,refresh_token,expires_at}` are
all present and non-empty - reject before it ever touches disk, not after.
It then writes the file atomically to `/data/config.json` (temp file + fsync
+ rename, same mechanism as the routine token-refresh writes every ~6h - see
`config.py`), and kicks off an immediate re-render of every cached view
instead of waiting for the next 4-minute tick. **The server process does not
restart** - no downtime, the Pi never sees a gap.

## Rollback

Uploading a broken config can't brick the display: a failed render never
overwrites a good cache entry (see `_refresh_one` in `app.py`), so the Pi
keeps getting the last good PNGs for as long as that cache entry lives -
effectively indefinitely, since only a *successful* render replaces it.

- Fix the problem locally (re-run `setup_strava.py`, or check the Strava app
  credentials) and upload again with the same curl command.
- If you need to go back to a known-good config and don't have it locally:
  `[server] cat ~/stravaDisplay/data/config.json` before you overwrite
  anything, so you have a copy to restore from. There is no automatic
  backup of `data/config.json` - see the Known limitations in
  [../CLAUDE.md](../CLAUDE.md).
- Last resort, `[server]`:
  ```bash
  cd ~/stravaDisplay
  cp data/config.json data/config.json.bak   # before touching it
  # ... restore a known-good copy into data/config.json ...
  docker compose restart server
  ```

## Security note

`STRAVA_ADMIN_TOKEN` is a password, not a shared secret to paste into chat.
It gates both `/admin/bootstrap` (can overwrite the live Strava config) and
`/admin/cache`. Never commit it, never send it over Slack/email/etc.

If it leaks: generate a new one (`openssl rand -hex 32`), edit `.env` on the
server, then `[server] docker compose restart server`. The old token stops
working immediately.
