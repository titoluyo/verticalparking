#!/bin/bash
# Quick script to check camera availability

echo "Checking camera devices..."
echo ""

# List video devices
echo "Video devices:"
ls -l /dev/video* 2>/dev/null || echo "  No /dev/video* devices found"
echo ""

# Check if rpicam works
echo "Testing with rpicam-hello (5 second test)..."
if command -v rpicam-hello &> /dev/null; then
    timeout 5 rpicam-hello 2>&1 | head -5
    echo ""
    echo "✓ rpicam-hello can access camera"
else
    echo "  rpicam-hello not found (install: sudo apt install -y rpicam-apps)"
fi
echo ""

# Check v4l2 devices
echo "V4L2 devices:"
if command -v v4l2-ctl &> /dev/null; then
    v4l2-ctl --list-devices 2>/dev/null || echo "  v4l2-ctl found but no devices"
else
    echo "  v4l2-ctl not installed (install: sudo apt install -y v4l-utils)"
fi

