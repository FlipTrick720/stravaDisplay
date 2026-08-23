# systemctl
## Status
sudo systemctl status strava-display

## Stoppen (bis nächster Boot)
sudo systemctl stop strava-display

## Starten
sudo systemctl start strava-display

## Neustarten
sudo systemctl restart strava-display

## Live-Logs mitschauen
sudo journalctl -u strava-display -f

## Letzte 100 Zeilen ohne Live
sudo journalctl -u strava-display -n 100

## Auto-Start beim Boot deaktivieren
sudo systemctl disable strava-display

## Auto-Start wieder aktivieren
sudo systemctl enable strava-display

## Bei git pull auf dem Pi, dann:
sudo systemctl restart strava-display



# Ununtu Server
## Redeploy on Ubuntu server (after pull)
docker compose up -d --build

# Status
docker compose ps



For: 
WARN[0000] The "STRAVA_ADMIN_TOKEN" variable is not set. Defaulting to a blank string.

python3 -c "import secrets; print(secrets.token_hex(32))"