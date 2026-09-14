# Raspberry Pi Minimal Deployment Guide

Run these commands on the fresh Raspberry Pi (over SSH).

### 1. Download the Code
If `git` is already installed:
```bash
git clone https://github.com/FlipTrick720/stravaDisplay.git ~/stravaDisplay
```
*(If you already have a folder, you can just `cd ~/stravaDisplay && git pull`)*

### 2. Run the Prep Scripts
These scripts install all dependencies and the Waveshare e-paper drivers.
```bash
cd ~/stravaDisplay/setup
bash part1-preboot.sh
```
*(The Pi will automatically reboot at the end of Part 1. Wait a minute, SSH back in, and run Part 2)*
```bash
cd ~/stravaDisplay/setup
bash part2-postboot.sh
```

### 3. Install Python Requirements
```bash
cd ~/stravaDisplay/pi
pip install -r requirements.txt --break-system-packages
```

### 4. Create the Configuration
```bash
cd ~/stravaDisplay/pi
cp config.example.yaml config.yaml
```
*(The default `config.yaml` is already pointed at `https://strava-display.maltebraig.com`, so you don't even need to edit it!)*

### 5. Start the Display Service
Install it so it runs automatically in the background and starts on boot:
```bash
cd ~/stravaDisplay/pi
sudo cp strava-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable strava-display
sudo systemctl start strava-display
```

### Done! 🎉
You can check the live logs at any time to make sure it's downloading the images successfully:
```bash
journalctl -u strava-display -f
```

