#!/bin/bash

# Master installer for the Colonizer hardware node on Raspberry Pi 
#
# Installation is performed in two stages:
#   1. Python setup (virtual environment and dependencies)
#   2. System setup (service user, Supervisor, permissions and runtime configuration)
#
# This script must be run as root, for example:
#   sudo bash <script_name>.sh

set -euo pipefail
INSTALL_DIR="/app/Colonizer"

echo "=== Colonizer Hardware Node Installer ==="

# 1) Python/venv setup FIRST
bash "$INSTALL_DIR/Pi_running_only_hardware/install_python.sh"

# 2) System/Supervisor setup SECOND
bash "$INSTALL_DIR/Pi_running_only_hardware/install_system.sh"

echo "Pi Installation complete."

#Ignore errors on: lgpio (fails on Pi 5 because lgpio notifier cannot create .lgd-nfy*)