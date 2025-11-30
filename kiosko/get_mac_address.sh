#!/usr/bin/env bash
# Helper script to get MAC address(es) of network interfaces
# Useful for configuring static IP reservations in DD-WRT

set -euo pipefail

echo "Network Interface MAC Addresses"
echo "================================"
echo ""

# Get all network interfaces
INTERFACES=$(ip link show | grep -E "^[0-9]+:" | awk -F': ' '{print $2}' | grep -v lo)

if [ -z "$INTERFACES" ]; then
    echo "No network interfaces found."
    exit 1
fi

# Display MAC addresses for each interface
for iface in $INTERFACES; do
    MAC=$(ip link show "$iface" 2>/dev/null | grep -oP '(?<=link/ether )[^ ]+' || echo "N/A")
    STATE=$(ip link show "$iface" 2>/dev/null | grep -oP '(?<=state )[^ ]+' || echo "UNKNOWN")
    
    if [ "$MAC" != "N/A" ]; then
        # Format MAC address with colons (DD-WRT format)
        MAC_COLONS=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
        # Format MAC address with dashes (alternative format)
        MAC_DASHES=$(echo "$MAC" | tr ':' '-' | tr '[:lower:]' '[:upper:]')
        
        echo "Interface: $iface"
        echo "  State: $STATE"
        echo "  MAC Address (colons): $MAC_COLONS"
        echo "  MAC Address (dashes): $MAC_DASHES"
        
        # Highlight active interfaces
        if [ "$STATE" = "UP" ] || [ "$STATE" = "UNKNOWN" ]; then
            echo "  ⚠ This interface appears to be active"
        fi
        echo ""
    fi
done

# Try to identify the primary interface
echo "Primary Network Interface Detection:"
echo "-------------------------------------"

# Check for default route
DEFAULT_IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)

if [ -n "$DEFAULT_IFACE" ]; then
    MAC=$(ip link show "$DEFAULT_IFACE" 2>/dev/null | grep -oP '(?<=link/ether )[^ ]+' || echo "N/A")
    if [ "$MAC" != "N/A" ]; then
        MAC_COLONS=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
        echo "Default route interface: $DEFAULT_IFACE"
        echo "MAC Address: $MAC_COLONS"
        echo ""
        echo "→ Use this MAC address for DD-WRT static IP configuration"
    fi
fi

# Check for eth0 (common on Raspberry Pi)
if ip link show eth0 &>/dev/null; then
    MAC=$(ip link show eth0 | grep -oP '(?<=link/ether )[^ ]+')
    if [ -n "$MAC" ]; then
        MAC_COLONS=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
        echo "Ethernet interface (eth0):"
        echo "MAC Address: $MAC_COLONS"
    fi
fi

# Check for wlan0 (wireless)
if ip link show wlan0 &>/dev/null; then
    MAC=$(ip link show wlan0 | grep -oP '(?<=link/ether )[^ ]+')
    if [ -n "$MAC" ]; then
        MAC_COLONS=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
        echo "Wireless interface (wlan0):"
        echo "MAC Address: $MAC_COLONS"
    fi
fi

echo ""
echo "Note: Copy the MAC address (with colons) to use in DD-WRT static lease configuration."

