# ssh
ssh malte@192.168.178.49
ssh flip@stravadisplay
44b0501dfeab29ea4794a3ec0b79f6eaa9c56009a8eed011a5936989cdd4010e

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

## Status
docker compose ps
## Logs
docker compose logs server --tail=30 --follow

## Stop server (not cloudflaire tunnel)
docker compose stop server
## Start
docker compose start server

## Alle container stoppen
docker compose stop
## Starten
docker compose start



