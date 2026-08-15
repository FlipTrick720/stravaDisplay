# Strava Display

E-paper display showing Strava stats. Raspberry Pi Zero WH + Waveshare 7.5" e-Paper HAT V2.

## Hardware
- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800x480)
- microSD 16GB+
- 5V/2.5A power supply

## Setup

Flash Raspberry Pi OS Lite via Raspberry Pi Imager. Pre-configure:
- Hostname, user, WiFi, SSH enabled

SSH into the Pi, then:

```bash
git clone https://github.com/FlipTrick720/stravaDisplay.git
cd stravaDisplay
./setup/01-system.sh
sudo reboot
# wait 10 min, ssh back in
./setup/02-waveshare.sh
./setup/03-python-deps.sh
```

## Configuration

Copy `config.example.json` to `config.json` and fill in your Strava credentials.
