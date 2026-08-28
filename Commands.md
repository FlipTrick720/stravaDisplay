# ssh
ssh malte@192.168.178.49
ssh flip@stravadisplay

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



For: 
WARN[0000] The "STRAVA_ADMIN_TOKEN" variable is not set. Defaulting to a blank string.
Use:
python3 -c "import secrets; print(secrets.token_hex(32))"


Feature:

what about a feature on the pi that remembers what was the last view was so the pi can restart from time to time without anybody noticing and continuting exactly where it left of


# Generell
## Keine KI Commits
mkdir -p ~/.claude && cat << 'EOF' > ~/.claude/settings.json
{
  "deny": [
    "Bash(git commit*)",
    "Bash(git push*)",
    "Bash(git add*)",
    "Bash(git reset*)",
    "Bash(git stash*)"
  ]
}
EOF

