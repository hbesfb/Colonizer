#!/bin/bash

# This script creates and populates the Python virtual environment required
# by the Colonizer hardware node. It installs all Python dependencies into
# the venv and prepares the runtime environment before Supervisor and the
# service user are configured.
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

echo "==> Installing system packages..."
apt install -y --no-install-recommends \
    python3-venv=3.13.5-1 \
    libgl1=1.7.0-1+b2 \
    libcamera-dev=0.7.2+rpt20260817-1 \
    libcap-dev=1:2.75-10+deb13u1+b1 \
    python3-libcamera=0.7.2+rpt20260817-1 \
    python3-kms++=0~git20250807.1813ada-1 \
    python3-opencv=4.10.0+dfsg-5

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
