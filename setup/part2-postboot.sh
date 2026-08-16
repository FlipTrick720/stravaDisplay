#!/bin/bash
# Part 2: Waveshare Library + Python packages + Verifikation
set -e

echo "=== [1/4] SPI-Check ==="
if [ ! -e /dev/spidev0.0 ]; then
  echo "FEHLER: /dev/spidev0.0 nicht da. Wurde part1 gelaufen + reboot?"
  exit 1
fi
echo "SPI ok"

echo "=== [2/4] Waveshare Library ==="
cd ~
if [ ! -d e-Paper ]; then
  git clone https://github.com/waveshareteam/e-Paper.git
else
  echo "Waveshare repo existiert bereits, skip clone"
fi

cd ~/e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install || true
# Jetson.GPIO Fehler am Ende ist bekannt und unkritisch

echo "=== [3/4] Python packages via pip ==="
python3 -m pip install polyline --break-system-packages

sync

echo ""
echo "=== [4/4] Verifikation ==="
python3 -c "from waveshare_epd import epd7in5_V2; print('  waveshare_epd: ok')"
python3 -c "import requests; print(f'  requests: ok ({requests.__version__})')"
python3 -c "from PIL import Image, ImageDraw, ImageFont; print('  PIL: ok')"
python3 -c "import spidev; print('  spidev: ok')"
python3 -c "import polyline; print(f'  polyline: ok ({polyline.__version__})')"

echo ""
echo "=============================================="
echo "  PART 2 DONE"
echo "=============================================="
