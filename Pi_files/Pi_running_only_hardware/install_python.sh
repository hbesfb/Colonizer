#!/bin/bash

# This script runs Python code inside the venv, as user colonizer, so that
# import validation happens exactly the same way the daemon will run under Supervisor.

set -euo pipefail

INSTALL_DIR="/app/Colonizer"
SERVICE_USER="colonizer"
REQUIREMENTS_FILE="Pi_running_only_hardware/requirements_hw.txt"

echo "=== Colonizer Hardware Node Installer (Python Setup) ==="

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)."
    exit 1
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "ERROR: Install directory $INSTALL_DIR does not exist."
    exit 1
fi
echo "debug: =====> running apt update"
# update apt
apt update
apt upgrade -y

echo "==> Installing system packages..."
apt install -y --no-install-recommends \
    python3-venv \
    libgl1 \
    libcamera-dev \
    libcap-dev \
    python3-libcamera \
    python3-kms++ \
    python3-opencv

echo "==> Creating Python virtual environment..."
cd "$INSTALL_DIR"

echo "==> Stopping any running colonizer-hw process before rebuilding venv..."
supervisorctl stop colonizer-hw 2>/dev/null || true
pkill -9 -f "hwlayer.server" || true
for i in {1..20}; do
    pgrep -f "hwlayer.server" >/dev/null 2>&1 || break
    sleep 0.25
done

echo "Deleting existing virtual environment (if any)..."
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip

echo "==> Installing hardware-specific Python requirements..."
REQ_FILE="$INSTALL_DIR/$REQUIREMENTS_FILE"
if [[ ! -f "$REQ_FILE" ]]; then
    echo "ERROR: Requirements file not found: $REQ_FILE"
    exit 1
fi

pip install -r "$REQ_FILE" || {
    echo "ERROR: Failed to install Python hardware dependencies."
    exit 1
}


echo "Python setup complete."
