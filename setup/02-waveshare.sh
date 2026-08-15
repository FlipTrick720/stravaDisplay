#!/bin/bash
# Waveshare e-Paper Library installieren
set -e

cd ~
if [ ! -d e-Paper ]; then
  echo "=== Clone Waveshare repo ==="
  git clone https://github.com/waveshareteam/e-Paper.git
else
  echo "=== Waveshare repo existiert bereits ==="
fi

echo "=== Install Waveshare Python library ==="
cd ~/e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install || true
# Jetson.GPIO Fehler am Ende ignorieren - Library ist trotzdem installiert

sync
echo "=== 02-waveshare.sh DONE ==="
