"""
## Strava API (do this on your dev machine, not the Pi)

1. Register app at https://www.strava.com/settings/api
   - Name: anything without "Strava" in it
   - Category: Data Importer
   - Website: `http://localhost`
   - Callback Domain: `localhost`
   - Any 124×124+ logo (e.g. https://picsum.photos/200)
2. Copy `config.example.json` to `config.json`
3. Fill in `client_id` and `client_secret`
4. Run this scipt:
    ```bash
    python3 src/setup_strava.py
    ```

STILL THE ENTRY POINT for getting tokens. Run it LOCALLY (it needs a browser
for the OAuth redirect, so it cannot run unattended in the container), then
push the resulting config.json to the deployed server:

    cd server && python3 setup_strava.py          # writes ../config.json
    curl -X POST \\
         -H "Authorization: Bearer $STRAVA_ADMIN_TOKEN" \\
         -F "config=@config.json" \\
         https://strava-display.maltebraig.com/admin/bootstrap

The bootstrap endpoint validates the file, writes it atomically to the
server's config volume, and triggers an immediate re-render. That replaces the
old scp-into-data/ step. See docs/DEPLOYMENT.md.

Run this again whenever the refresh token stops being accepted.

It walks through the OAuth flow manually - no local webserver needed. Flow:

  1. Prints authorization URL. Open it in browser.
  2. Authorize the app for your Strava account.
  3. Strava redirects to http://localhost/?code=XYZ&scope=...
     Browser will show "connection refused" - that's fine, we just need the URL.
  4. Copy the 'code' query param from the URL.
  5. Paste it here.
  6. Script exchanges code for access + refresh token.
  7. Writes tokens into config.json.

After this, display.py can just fetch data - token refresh is automatic.
"""
import sys
import requests
from urllib.parse import urlencode

import config

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/api/v3/oauth/token"
REDIRECT_URI = "http://localhost"
SCOPES = "read,activity:read_all,profile:read_all"


def main():
    cfg = config.load()
    client_id = cfg["strava"]["client_id"]
    client_secret = cfg["strava"]["client_secret"]

    if not client_id or not client_secret:
        print("ERROR: client_id and client_secret must be set in config.json first.")
        sys.exit(1)

    # Step 1: build authorize URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": SCOPES,
    }
    auth_url = f"{STRAVA_AUTHORIZE_URL}?{urlencode(params)}"

    print("=" * 70)
    print("Strava OAuth Setup")
    print("=" * 70)
    print()
    print("Step 1: Open this URL in your browser:")
    print()
    print(f"  {auth_url}")
    print()
    print("Step 2: Authorize the app. You'll be redirected to a URL like:")
    print("  http://localhost/?state=&code=ABC123DEF456...&scope=read,activity:read_all,...")
    print("  Browser will show 'connection refused' - that's expected.")
    print()
    print("Step 3: Copy the value of 'code' from the URL.")
    print()

    code = input("Paste code here: ").strip()
    if not code:
        print("ERROR: no code entered.")
        sys.exit(1)

    # Step 2: exchange code for tokens
    print("\nExchanging code for tokens...")
    resp = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )

    if not resp.ok:
        print(f"ERROR: Strava returned {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    data = resp.json()

    # Step 3: save to config
    cfg["strava"]["access_token"] = data["access_token"]
    cfg["strava"]["refresh_token"] = data["refresh_token"]
    cfg["strava"]["expires_at"] = data["expires_at"]
    config.save(cfg)

    athlete = data.get("athlete", {})
    print()

    print("=" * 70)
    print(f"SUCCESS - logged in as {athlete.get('firstname')} {athlete.get('lastname')}")
    print("Tokens saved to config.json")
    print("=" * 70)


    print()
    push = input("Do you want to upload this config to your deployed server now? (y/n): ").strip().lower()
    if push == 'y':
        server_url = "https://strava-display.maltebraig.com"
        
        # Try to read token from .env automatically
        admin_token = ""
        try:
            with open("../.env", "r") as env_file:
                for line in env_file:
                    if line.startswith("STRAVA_ADMIN_TOKEN="):
                        admin_token = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass
            
        if not admin_token:
            admin_token = input("Enter STRAVA_ADMIN_TOKEN: ").strip()
        else:
            print(f"Found admin token in .env file!")
        
        print(f"Uploading config.json to {server_url}/admin/bootstrap...")
        try:
            with open(config.CONFIG_PATH, "rb") as f:
                r = requests.post(
                    f"{server_url}/admin/bootstrap",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    files={"config": f},
                    timeout=15
                )
            if r.ok:
                print("SUCCESS - config uploaded and server refreshed!")
            else:
                print(f"ERROR: Server responded with {r.status_code}")
                print(r.text)
        except Exception as e:
            print(f"ERROR: Failed to connect to server - {e}")




if __name__ == "__main__":
    main()
