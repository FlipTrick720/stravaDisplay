# Strava Display

E-paper dashboard showing Strava cycling stats. Raspberry Pi Zero WH + Waveshare 7.5" e-Paper HAT V2.

## Hardware
- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800×480)
- microSD card
- 5V/2.5A power supply

## Pi Setup

Flash Raspberry Pi OS Lite via Raspberry Pi Imager. Pre-configure hostname, user, WiFi, SSH.

SSH into the Pi:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/FlipTrick720/stravaDisplay.git
cd stravaDisplay

./setup/part1-preboot.sh   # ~30-60 min, auto-reboots

# After reboot, SSH back in:
cd stravaDisplay
./setup/part2-postboot.sh  # ~15-25 min
```

Verify display:
```bash
python3 ~/e-Paper/RaspberryPi_JetsonNano/python/examples/epd_7in5_V2_test.py
```

## Strava API

1. Register app at https://www.strava.com/settings/api
   - Name: anything without "Strava" in it (trademark)
   - Website: `http://localhost`
   - Callback Domain: `localhost`
   - Any 124×124+ logo (e.g. https://picsum.photos/200)
2. Copy `config.example.json` to `config.json`
3. Fill in `client_id` and `client_secret`
4. Run OAuth once:
```bash
   python3 src/setup_strava.py
```
   - Paste code from redirected URL in browser back in.

## Development

Preview renders as PNG (no Pi needed):
```bash
python3 src/renderer.py           # overview
python3 src/renderer.py latest    # single activity
```

Run tests:
```bash
python3 tests/test_aggregator.py
```

## Rules

**Never yank power.** Always:
```bash
sudo shutdown -h now
```
Wait until green LED is off. Otherwise SD corruption. I learned the hard way.

## Case dimensions (3D print)
- Display active area: 170.2 × 111.2 mm
- Full display panel: 178.85 × 121.98 × 1.18 mm
- Driver HAT: 65 × 30.2 × 15 mm
