#!/bin/bash
# Python packages via pip
set -e

echo "=== stravalib installieren ==="
python3 -m pip install stravalib --break-system-packages

sync
echo "=== 03-python-deps.sh DONE ==="
