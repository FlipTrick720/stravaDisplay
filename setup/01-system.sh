#!/bin/bash
# System update + SPI aktivieren + Basis-Dependencies
set -e

echo "=== [1/3] System update ==="
sudo apt update && sudo apt upgrade -y

echo "=== [2/3] SPI aktivieren ==="
sudo raspi-config nonint do_spi 0

echo "=== [3/3] Dependencies ==="
sudo apt install -y \
  python3-pip \
  python3-pil \
  python3-numpy \
  python3-spidev \
  python3-rpi.gpio \
  python3-requests \
  git

sync
echo "=== 01-system.sh DONE. Reboot empfohlen. ==="
