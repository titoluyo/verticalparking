#!/usr/bin/env bash
# Setup script to configure Raspberry Pi hostname as "control.local"
# This enables mDNS (multicast DNS) so the Pi can be accessed as "control.local"
# Run with: sudo bash setup_hostname.sh

set -euo pipefail

HOSTNAME="control"

echo "Setting up Raspberry Pi hostname as '${HOSTNAME}.local'..."

# 1. Set the hostname
echo "Setting hostname to '${HOSTNAME}'..."
hostnamectl set-hostname "${HOSTNAME}"

# Update /etc/hosts if needed
if ! grep -q "^127.0.1.1.*${HOSTNAME}" /etc/hosts 2>/dev/null; then
    echo "Updating /etc/hosts..."
    # Remove any existing entry for this hostname
    sed -i "/127.0.1.1.*${HOSTNAME}/d" /etc/hosts 2>/dev/null || true
    # Add new entry
    echo "127.0.1.1	${HOSTNAME}" | tee -a /etc/hosts
fi

# 2. Install Avahi daemon if not already installed
if ! command -v avahi-daemon &> /dev/null; then
    echo "Installing Avahi daemon..."
    apt-get update
    apt-get install -y avahi-daemon avahi-utils
else
    echo "Avahi daemon is already installed."
fi

# 3. Ensure Avahi service is enabled and running
echo "Starting and enabling Avahi daemon..."
systemctl enable avahi-daemon
systemctl restart avahi-daemon

# 4. Verify Avahi is running
if systemctl is-active --quiet avahi-daemon; then
    echo "✓ Avahi daemon is running"
else
    echo "✗ Warning: Avahi daemon is not running. Check with: sudo systemctl status avahi-daemon"
    exit 1
fi

# 5. Display current status
echo ""
echo "Configuration complete!"
echo "Current hostname: $(hostname)"
echo ""
echo "You can now access this Raspberry Pi as:"
echo "  - ${HOSTNAME}.local"
echo "  - $(hostname -I | awk '{print $1}')"
echo ""
echo "To verify mDNS is working, run on another device:"
echo "  ping ${HOSTNAME}.local"
echo "  or"
echo "  avahi-resolve -n ${HOSTNAME}.local"
echo ""
echo "Note: It may take a few seconds for mDNS to propagate on the network."

