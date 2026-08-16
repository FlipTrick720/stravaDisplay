# Strava Display

E-paper display showing Strava stats. Raspberry Pi Zero WH + Waveshare 7.5" e-Paper HAT V2.

## Hardware
- Raspberry Pi Zero WH
- Waveshare 7.5" e-Paper HAT V2 (800x480)
- microSD
- 5V/2.5A power supply (offizielles Raspberry Pi Netzteil)

## Dependencies
- python3-requests (system package) - Strava API calls
- python3-pil - Image rendering
- Waveshare e-Paper library - Display driver

## Setup

Flash Raspberry Pi OS Lite via Raspberry Pi Imager. Pre-configure:
- Hostname, user, WiFi, SSH enabled etc.

SSH into the Pi, then:

### Setup
```bash
# Install Git
sudo apt update
sudo apt install -y git

# Clone Repo
git clone https://github.com/FlipTrick720/stravaDisplay.git
cd stravaDisplay

# Part 1: ~30-60 min. Ends with automatic reboot.
./setup/part1-preboot.sh

# After reboot, SSH back in:
cd stravaDisplay

# Part 2: ~15-25 min. Ends with verification.
./setup/part2-postboot.sh
```
### Test Display
```bash
cd ~/e-Paper/RaspberryPi_JetsonNano/python/examples
python3 epd_7in5_V2_test.py
```

## Strava API registrieren
### Schritt 1: Strava Account einloggen
Geh zu: **https://www.strava.com/settings/api**

### Schritt 2: App-Formular ausfüllen

| Feld | Wert |
|---|---|
| **Application Name** | `E-Paper Stats Display` |
| **Category** | `Data Importer` |
| **Club** | leer lassen |
| **Website** | `http://localhost` |
| **Application Description** | `Personal e-paper display for Strava stats` |
| **Authorization Callback Domain** | `localhost` |

### Schritt 3: Logo hochladen (Pflicht!)

Logo (mind. 124x124 px). (**https://picsum.photos/200**)

### Schritt 4: Configuration In Repo

Copy `config.example.json` to `config.json` and fill in your Strava credentials.

# 3d-Druck
**Display-Panel**: 170.2 × 111.2 mm
**Ganzes Display-Panel**: 178.85 × 121.98 × 1.18 mm
**Driver HAT**: 65 × 30.2 x 15 mm
