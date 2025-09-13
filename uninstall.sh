#!/bin/bash

set -e

INSTALL_DIR="/opt/btrfs-snapshot-manager"
CONFIG_DIR="/etc/btrfs-snapshot-manager"
SERVICE_NAME="btrfs-snapshot-manager"
SYSTEMD_DIR="/etc/systemd/system"

echo "====================================="
echo "Btrfs Snapshot Manager Uninstallation"
echo "====================================="

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

echo "Stopping service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

echo "Disabling service..."
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

echo "Removing service file..."
rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service"
systemctl daemon-reload

echo "Removing installation directory..."
rm -rf "$INSTALL_DIR"

read -p "Remove configuration directory $CONFIG_DIR? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo "Configuration removed."
else
    echo "Configuration preserved at $CONFIG_DIR"
fi

read -p "Remove log file /var/log/btrfs_snapshot.log? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f /var/log/btrfs_snapshot.log*
    echo "Log files removed."
else
    echo "Log files preserved."
fi

echo ""
echo "Uninstallation complete!"