# Pi Setup

Installing the e-paper client. The Pi only fetches PNGs and pushes pixels; the
server does everything else.

## Prerequisites

- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800x480), seated on the GPIO header
- Raspberry Pi OS Lite, with SSH and WiFi configured via Raspberry Pi Imager
- The server reachable at `https://strava-display.maltebraig.com`

SPI must be enabled:

```bash
sudo raspi-config    # Interface Options -> SPI -> Enable
```

The Waveshare Python driver (`waveshare_epd`) comes from their repo. If you have
not installed it yet, run `setup/part1-preboot.sh` and `setup/part2-postboot.sh`
from the repo root first.

Verify the panel before going further:

```bash
python3 ~/e-Paper/RaspberryPi_JetsonNano/python/examples/epd_7in5_V2_test.py
```

## Install

```bash
git clone https://github.com/FlipTrick720/stravaDisplay.git ~/stravaDisplay
cd ~/stravaDisplay/pi

pip install -r requirements.txt --break-system-packages
```

## Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Defaults match the deployed server, so an unedited copy works. Change
`server_url` if the domain moves, or trim `views` to drop the weekly
placeholder until Phase 2 lands.

## Test

```bash
python3 display.py once
```

Fetches one view, writes `preview.png` next to the script, and pushes to the
panel. Expect log lines like:

```
2026-08-22 20:15:03 [INFO] Fetched weekly (891 bytes, server rendered at 2026-08-22T18:13:44+00:00)
2026-08-22 20:15:06 [INFO] Pushed weekly to display
```

If the server is unreachable it falls back to the cached PNG, then to
`fallback/no-server.png`. That is expected behaviour, not a failure.

## Install the service

```bash
sudo cp strava-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable strava-display
sudo systemctl start strava-display
```

The unit assumes user `flip` and `/home/flip/stravaDisplay/pi`. Edit `User=`
and `WorkingDirectory=` if yours differ.

## Logs

```bash
journalctl -u strava-display -f          # follow
journalctl -u strava-display -n 100      # last 100 lines
journalctl -u strava-display --since "1 hour ago"
```

## Operating

```bash
sudo systemctl restart strava-display
sudo systemctl stop strava-display
systemctl status strava-display
```

After pulling new code:

```bash
cd ~/stravaDisplay && git pull
sudo systemctl restart strava-display
```

## Troubleshooting

**Panel stays blank.** SPI enabled? `waveshare_epd` importable?

```bash
python3 -c "from waveshare_epd import epd7in5_V2; print('driver ok')"
```

**Service restarts in a loop then gives up.** The unit allows 3 starts per 5
minutes. Read the actual error, fix it, then `sudo systemctl reset-failed
strava-display` before starting again.

**Always shows the fallback image.** The Pi cannot reach the server:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://strava-display.maltebraig.com/health
```

**Stale image.** The server re-renders every 4 minutes. Each fetch logs the
server's `X-Generated-At`; if that timestamp is not advancing, the problem is
server-side, not on the Pi. See `docs/OPERATIONS.md`.

## Rules

**Never yank power.** Always:

```bash
sudo shutdown -h now
```

Wait until the green LED is off. Otherwise SD corruption.
