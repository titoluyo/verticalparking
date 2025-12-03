#!/bin/bash
# Install system dependencies for camera QR code reading on Raspberry Pi

set -e

echo "Installing camera dependencies for Raspberry Pi..."
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/cpuinfo ] || ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "Warning: This script is designed for Raspberry Pi"
    echo "Continuing anyway..."
    echo ""
fi

# Update package list
echo "Updating package list..."
sudo apt update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y \
    python3-opencv \
    libzbar0 \
    libcap-dev \
    python3-dev \
    build-essential \
    python3-pip

echo ""
echo "✓ System dependencies installed"
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not active"
    echo "Activate your venv and run: pip install picamera2"
else
    echo "Installing picamera2 in virtual environment..."
    pip install picamera2
    echo "✓ picamera2 installed"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Enable camera: sudo raspi-config → Interface Options → Camera → Enable"
echo "2. Reboot if you enabled the camera"
echo "3. Test with: python test_camera_qr.py"

