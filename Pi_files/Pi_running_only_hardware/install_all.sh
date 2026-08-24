#!/bin/bash
# This is the master script that installs the Colonizer hardware node on a Raspberry Pi (Debian 13 /Pi 5). 
# It calls the other scripts in this directory to perform the installation steps.
# it should be run as root (sudo) to ensure that all steps can be completed successfully. ie
#  `sudo -E bash <script_name>.sh` to preserve the environment variables
set -euo pipefail
INSTALL_DIR="/app/Colonizer"

echo "=== Colonizer Hardware Node Installer ==="

# 1) Python/venv setup FIRST
bash "$INSTALL_DIR/Pi_running_only_hardware/install_python.sh"

# 2) System/Supervisor setup SECOND
bash "$INSTALL_DIR/Pi_running_only_hardware/install_system.sh"

echo "Pi Installation complete."

#Ignore errors on: lgpio (fails on Pi 5 because lgpio notifier cannot create .lgd-nfy*)