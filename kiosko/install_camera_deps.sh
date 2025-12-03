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
    python3-dev \
    build-essential \
    python3-pip \
    v4l-utils

echo ""
echo "✓ System dependencies installed"
echo ""

# Check camera access
echo "Checking camera access..."
if [ -e /dev/video0 ] || [ -e /dev/video1 ]; then
    echo "✓ Camera device found"
    ls -l /dev/video* 2>/dev/null || true
else
    echo "⚠ No camera device found at /dev/video*"
    echo "  Make sure camera is connected"
fi

echo ""

# Note: picamera2 is optional - OpenCV works fine with Raspberry Pi camera
echo "Note: picamera2 is optional. OpenCV can access the camera directly."
echo "If you want to install picamera2 (may require libcap-dev):"
echo "  sudo apt install -y libcap-dev"
echo "  pip install picamera2"
echo ""

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not active"
    echo "Activate your venv and run: pip install -r requirements.txt"
else
    echo "Installing Python dependencies (picamera2 is optional)..."
    pip install opencv-python pyzbar
    echo "✓ Basic camera dependencies installed"
    echo ""
    echo "Optional: Install picamera2 (if needed):"
    echo "  sudo apt install -y libcap-dev"
    echo "  pip install picamera2"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Test the camera:"
echo "  python test_camera_qr.py"
echo ""
echo "The script uses OpenCV which works with the Raspberry Pi camera via V4L2."

