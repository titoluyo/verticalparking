#!/usr/bin/env python3
"""
Simple test: Capture one image from Raspberry Pi camera and read QR code.
Start simple, then we can add video streaming.
"""

import subprocess
import sys
import os

# Test 1: Capture image with rpicam-still
print("=" * 60)
print("Simple Camera Test")
print("=" * 60)
print("\nTest 1: Capturing image with rpicam-still...")
result = subprocess.run(
    ['rpicam-still', '-o', 'test_image.jpg', '--timeout', '1000'],
    capture_output=True,
    timeout=5
)

if result.returncode != 0:
    print(f"✗ Failed to capture image")
    print(f"Error: {result.stderr.decode()}")
    sys.exit(1)

if not os.path.exists('test_image.jpg'):
    print("✗ Image file not created")
    sys.exit(1)

file_size = os.path.getsize('test_image.jpg')
print(f"✓ Image captured: test_image.jpg ({file_size} bytes)")

# Test 2: Read image with OpenCV
print("\nTest 2: Reading image with OpenCV...")
try:
    import cv2
    img = cv2.imread('test_image.jpg')
    if img is None:
        print("✗ Failed to read image with OpenCV")
        sys.exit(1)
    print(f"✓ Image read: {img.shape[1]}x{img.shape[0]} pixels")
except ImportError:
    print("✗ OpenCV not installed")
    print("  Install with: pip install opencv-python")
    sys.exit(1)

# Test 3: Detect QR code
print("\nTest 3: Detecting QR code...")
try:
    from pyzbar import pyzbar
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    qr_codes = pyzbar.decode(gray)
    
    if qr_codes:
        for qr in qr_codes:
            print(f"✓ QR Code found: {qr.data.decode('utf-8')}")
    else:
        print("ℹ No QR code detected in image (this is OK for first test)")
        print("  Point a QR code at the camera and run again")
except ImportError:
    print("✗ pyzbar not installed")
    print("  Install with: pip install pyzbar")
    print("  Also install: sudo apt-get install libzbar0")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All tests passed! Camera is working.")
print("=" * 60)
print("\nNext step: Add video streaming for real-time QR detection.")

