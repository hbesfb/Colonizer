#!/bin/bash

# This script performs system-level configuration for the Colonizer hardware
# node. It:
#   - Installs and validates Supervisor
#   - Creates the service account if required
#   - Grants GPIO and camera access
#   - Installs Supervisor configuration
#   - Configures permissions and ownership
#   - Creates required data directories
#   - Starts and validates the Colonizer hardware service

set -euo pipefail

INSTALL_DIR="/app/Colonizer"
SERVICE_USER="colonizer"
HARDWARE_TRANSPORT="${HARDWARE_TRANSPORT:-tcp}"
SETTLEPLATE_CONFIG="${SETTLEPLATE_CONFIG:-kubernetes}"

echo "=== Colonizer Hardware Node Installer (System Setup) ==="

# Must run as root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)."
    exit 1
fi

echo "==> Installing Supervisor..."
apt install -y --no-install-recommends supervisor

echo "==> Validating system dependencies..."
required_bins=(
    "python3"
    "pip3"
    "supervisord"
    "supervisorctl"
)

for bin in "${required_bins[@]}"; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        echo "ERROR: Required system binary '$bin' is missing."
        echo "Install it using:"
        echo "    sudo apt install python3 python3-venv python3-pip supervisor"
        exit 1
    fi
done
echo "System dependencies validated."

echo "==> Creating service user (if missing)..."
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd -m -s /usr/sbin/nologin "$SERVICE_USER"
fi

echo "==> Granting GPIO and camera access..."
usermod -a -G gpio "$SERVICE_USER"
usermod -a -G video "$SERVICE_USER"

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "ERROR: Install directory $INSTALL_DIR does not exist."
    exit 1
fi

SRC_CONF="$INSTALL_DIR/install/etc/supervisor/conf.d/colonizer_hw.conf"
DEST_CONF="/etc/supervisor/conf.d/"

# setup supervisor
if [ -d "$INSTALL_DIR/install/etc/supervisor" ]; then
  echo "==> Clearing old Supervisor configs..."
  rm -f $DEST_CONF/colonizer_hw.conf
  cp  "$SRC_CONF" "$DEST_CONF/colonizer_hw.conf"
  echo "==> Installing main Supervisor config..."
  cp "$INSTALL_DIR/install/etc/supervisor/supervisord.conf" /etc/supervisor/
else
echo "ERROR: This Supervisor config directory missing: $INSTALL_DIR/install/etc/supervisor"
  exit 1
fi

echo "==> Stopping any running Supervisor instance before validation..."
systemctl stop supervisor || true
rm -f /run/colonizer-supervisor-web.sock

# Kill any existing hwlayer.server processes before restarting Supervisor.
# This prevents startup conflicts caused by stale or orphaned processes from
# previous installations, crash loops, or failed service restarts.
echo "==> Killing any orphaned colonizer-hw processes..."
pkill -9 -f "hwlayer.server" || true

# wait for it to actually die, don't just fire-and-forget
for i in {1..20}; do
    pgrep -f "hwlayer.server" >/dev/null || break
    sleep 0.25
done

if pgrep -f "hwlayer.server" >/dev/null 2>&1; then
    echo "ERROR:hwlayer.server process still present after wait, exiting installation..."
    exit 1
fi

echo "==> Clearing old Colonizer logs..."
rm -f /var/log/colonizer-hw*

# Ensure the service user owns the installation directory before Supervisor
# starts the application. This allows the service to access the virtual
# environment, application files and logs without requiring root privileges.
echo "==> Setting ownership of install directory (before starting Supervisor)..."
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"

echo "==> Ensuring parent directories are traversable by $SERVICE_USER..."
chmod o+x /app || true

echo "==> Validating Supervisor configuration..."
if ! supervisord -c /etc/supervisor/supervisord.conf -t; then
    echo "ERROR: Supervisor configuration is invalid."
    exit 1
fi

echo "==> Enabling and starting Supervisor..."
systemctl enable supervisor
systemctl restart supervisor

echo "==> Waiting for Supervisor to become ready..."
for i in {1..10}; do
    if supervisorctl status >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

echo "==> Reloading Supervisor programs..."
supervisorctl reread
supervisorctl update
supervisorctl restart colonizer-hw || true

if supervisorctl status colonizer-hw | grep -q "ERROR"; then
    echo "!!! colonizer-hw failed to spawn. Last supervisord log lines:"
    tail -n 20 /var/log/supervisor/supervisord.log || true
fi

echo "==> Installing log rotation configs..."
LOGROTATE_CONFIGS=(
    "colonizer-hw"
    "colonizer-supervisor"
)

for conf in "${LOGROTATE_CONFIGS[@]}"; do
    LOGROTATE_SRC="$INSTALL_DIR/install/maintenance/$conf"

    if [[ ! -f "$LOGROTATE_SRC" ]]; then
        echo "ERROR: Logrotate config missing: $LOGROTATE_SRC"
        echo "This file is required to prevent SD-card log growth."
        exit 1
    fi

    cp "$LOGROTATE_SRC" /etc/logrotate.d/
    chown root:root "/etc/logrotate.d/$conf"
    chmod 644 "/etc/logrotate.d/$conf"
done

echo "==> Creating local data directory if it doesn't exist..."
mkdir -p /mnt/data/Data/Colonizer

echo "==> Setting ownership of install directory..."
chown "$SERVICE_USER":"$SERVICE_USER" /mnt/data/Data/Colonizer # set dir owner

# Service user has full access; group has read/execute access; others have no access.
chmod 750 /mnt/data/Data/Colonizer

# Create a minimal libcamera user configuration file. libcamera
# installation emits warnings and fails to locate a writable user
# configuration unless this directory and file exist.
echo "==> Ensuring libcamera config directory exists for colonizer user..."
sudo mkdir -p /home/$SERVICE_USER/.config/libcamera
echo "version: 1" | sudo tee /home/$SERVICE_USER/.config/libcamera/configuration.yaml >/dev/null
sudo chown -R $SERVICE_USER:$SERVICE_USER /home/$SERVICE_USER/.config/libcamera

echo "==> Ensuring libcamera config directory exists for admin user..."
sudo mkdir -p /home/admin/.config/libcamera
echo "version: 1" | sudo tee /home/admin/.config/libcamera/configuration.yaml >/dev/null
sudo chown -R admin:admin /home/admin/.config/libcamera

# Perform a final service restart now that all configuration,
# permissions and runtime directories are in place.
echo "==> Final restart of colonizer-hw now that setup is complete..."
supervisorctl restart colonizer-hw || true
sleep 2

if supervisorctl status colonizer-hw | grep -q "ERROR"; then
    echo "!!! colonizer-hw failed final restart. Last supervisord log lines:"
    tail -n 20 /var/log/supervisor/supervisord.log || true
fi

echo "=== System setup complete ==="
echo "Supervisor status:"
supervisorctl status colonizer-hw || true