#!/usr/bin/env bash
# Quick setup script for Cashino KP-300 thermal printer
# Run this script after a fresh Raspberry Pi installation

set -euo pipefail

echo "=========================================="
echo "Cashino KP-300 Printer Setup Script"
echo "=========================================="
echo ""

# Check if running as root for system commands
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run this script as root/sudo"
   echo "It will prompt for sudo when needed"
   exit 1
fi

# Step 1: Install system dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y libusb-1.0-0-dev

# Step 2: Install Python dependencies
echo ""
echo "[2/5] Installing Python dependencies..."
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 3: Create udev rule
echo ""
echo "[3/5] Creating USB permissions rule..."
UDEV_RULE="/etc/udev/rules.d/99-escpos-printer.rules"
sudo tee "$UDEV_RULE" > /dev/null << 'EOF'
# Cashino KP-300 via ICS Advent Parallel Adapter
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fe6", ATTRS{idProduct}=="811e", MODE="0666", GROUP="dialout"
EOF

echo "Udev rule created at $UDEV_RULE"

# Step 4: Reload udev rules
echo ""
echo "[4/5] Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

# Step 5: Add user to dialout group
echo ""
echo "[5/5] Adding user to dialout group..."
sudo usermod -a -G dialout "$USER"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "IMPORTANT: You must log out and log back in"
echo "for group membership changes to take effect."
echo ""
echo "To test immediately without logging out:"
echo "  newgrp dialout"
echo "  cd ~/verticalparking/kiosko"
echo "  source .venv/bin/activate"
echo "  python3 -c \"from escpos.printer import Usb; p = Usb(0x0fe6, 0x811e); p.text('Test\n'); p.cut(); p.close()\""
echo ""
echo "Or test via API (after starting Flask app):"
echo "  curl -X POST http://localhost:5000/api/printer/test"
echo ""

