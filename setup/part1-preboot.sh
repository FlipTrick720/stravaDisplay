#!/bin/bash
# Part 1: System update, SPI aktivieren, Basis-Dependencies
# Am Ende: Reboot (nötig damit SPI aktiv wird)
set -e

echo "=== [1/4] apt update ==="
sudo apt update

echo "=== [2/4] apt upgrade (dauert ewig auf Zero WH, geh Kaffee holen) ==="
sudo apt upgrade -y

echo "=== [3/4] Alle System-Dependencies ==="
sudo apt install -y \
  python3-pip \
  python3-pil \
  python3-numpy \
  python3-spidev \
  python3-rpi.gpio \
  python3-requests \
  git

echo "=== [4/4] SPI aktivieren ==="
sudo raspi-config nonint do_spi 0

sync

echo ""
echo "=============================================="
echo "  PART 1 DONE - REBOOT IN 10 SECONDS"
echo "  Nach reboot: SSH rein und part2 starten"
echo "=============================================="
sleep 10
sudo reboot
