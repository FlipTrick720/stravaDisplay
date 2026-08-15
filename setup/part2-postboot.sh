#!/bin/bash
# Part 2: Waveshare Library, stravalib, Verifikation
set -e

echo "=== [1/4] SPI-Check ==="
if [ ! -e /dev/spidev0.0 ]; then
  echo "FEHLER: /dev/spidev0.0 nicht da. Wurde part1 gelaufen + reboot?"
  exit 1
fi
echo "SPI ok"

echo "=== [2/4] Waveshare Library clonen ==="
cd ~
if [ ! -d e-Paper ]; then
  git clone https://github.com/waveshareteam/e-Paper.git
else
  echo "Waveshare repo existiert bereits, skip clone"
fi

echo "=== [3/4] Waveshare Python-Modul installieren ==="
cd ~/e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install || true
# Der Jetson.GPIO-Fehler am Ende ist bekannt und unkritisch

echo "=== [4/4] stravalib installieren ==="
python3 -m pip install stravalib --break-system-packages

sync

echo ""
echo "=== Verifikation ==="
python3 -c "from waveshare_epd import epd7in5_V2; print('  waveshare_epd: ok')"
python3 -c "import stravalib; print('  stravalib: ok')"

echo ""
echo "=============================================="
echo "  PART 2 DONE - System bereit zum Coden"
echo "=============================================="
