# Strava Display

E-paper display showing Strava stats. Raspberry Pi Zero WH + Waveshare 7.5" e-Paper HAT V2.

## Hardware
- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800x480)
- microSD
- 5V/2.5A power supply (offizielles Raspberry Pi Netzteil)

## Setup

Flash Raspberry Pi OS Lite via Raspberry Pi Imager. Pre-configure:
- Hostname, user, WiFi, SSH enabled

SSH into the Pi, then:

```bash
git clone https://github.com/FlipTrick720/stravaDisplay.git
cd stravaDisplay

# Part 1: ~30-60 min. Ends with automatic reboot.
./setup/part1-preboot.sh

# After reboot, SSH back in:
cd stravaDisplay

# Part 2: ~15-25 min. Ends with verification.
./setup/part2-postboot.sh
```

## Configuration

Copy `config.example.json` to `config.json` and fill in your Strava credentials.
