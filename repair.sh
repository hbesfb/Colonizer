#!/bin/bash
# Colonizer watchdog repair script
# Called automatically by watchdog when the system appears unhealthy.

LOGFILE="/var/log/colonizer-repair.log"

echo "=== Watchdog repair triggered at $(date) ===" >> "$LOGFILE"

# Kill VS Code Remote if running
if pidof node >/dev/null 2>&1; then
    echo "Killing VS Code Remote node process..." >> "$LOGFILE"
    kill $(pidof node) 2>/dev/null || true
fi

#try to restart Redis, if restart fails log to log file
echo "Restarting Redis..." >> "$LOGFILE"
systemctl restart redis || echo "Redis restart failed" >> "$LOGFILE"

echo "Restarting Supervisor (which restarts all Colonizer services)..." >> "$LOGFILE"
systemctl restart supervisor || echo "Supervisor restart failed" >> "$LOGFILE"

echo "Repair script completed at $(date)" >> "$LOGFILE"
exit 0