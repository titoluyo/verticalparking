# Camera QR Code Reader Setup

This guide explains how to set up and test the Raspberry Pi camera for QR code reading.

## Hardware Requirements

- **Raspberry Pi** (any model with camera connector)
- **Raspberry Pi Camera Module** (official camera or compatible)
- **USB Webcam** (alternative, works on Windows and Linux)

## Installation

### 1. Install System Dependencies

**On Raspberry Pi:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install camera libraries and QR code dependencies
sudo apt install -y python3-picamera2 python3-opencv libzbar0

# Enable camera interface (if not already enabled)
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
```

**On Windows:**
- No additional system dependencies needed
- OpenCV and PyZBar will be installed via pip

### 2. Install Python Dependencies

```bash
# Activate virtual environment
cd kiosko
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

This will install:
- `opencv-python` - Camera and image processing
- `pyzbar` - QR code detection
- `picamera2` - Raspberry Pi camera interface (Linux only)

## Testing the Camera

### Run the Test Script

```bash
python test_camera_qr.py
```

### Test Script Features

- **Automatic backend detection**: Uses `picamera2` on Raspberry Pi, OpenCV on Windows/Linux
- **Real-time QR detection**: Shows detected QR codes with overlay
- **Frame saving**: Press 's' to save current frame
- **Exit**: Press 'q' to quit

### Expected Output

```
============================================================
Camera QR Code Reader Test
============================================================

Controls:
  'q' - Quit
  's' - Save current frame

Starting camera...
Using camera backend: picamera2
✓ Raspberry Pi camera initialized

Camera ready! Point QR code at camera...
Press 'q' to quit

✓ QR Code detected: PARKING:abc12345
```

### Troubleshooting

#### Camera not detected on Raspberry Pi

1. **Check camera connection:**
   ```bash
   # Test camera with libcamera
   libcamera-hello --timeout 5000
   ```

2. **Enable camera interface:**
   ```bash
   sudo raspi-config
   # Interface Options → Camera → Enable
   # Reboot after enabling
   ```

3. **Check camera permissions:**
   ```bash
   # Add user to video group
   sudo usermod -a -G video $USER
   # Log out and back in
   ```

#### QR codes not detected

1. **Lighting**: Ensure good lighting on the QR code
2. **Distance**: QR code should be clearly visible (not too far/close)
3. **Focus**: Camera should be in focus
4. **Resolution**: Try adjusting frame resolution in script

#### OpenCV camera issues on Windows

1. **Check camera index:**
   - Default is camera 0
   - If you have multiple cameras, try changing `camera_index` in script

2. **Camera permissions:**
   - Windows may require camera permissions for the app
   - Check Windows Settings → Privacy → Camera

## QR Code Format

The system expects QR codes in the format:
```
PARKING:{token}
```

Where `{token}` is the unique token generated when storing a vehicle (UUID format).

Example QR code data:
```
PARKING:550e8400-e29b-41d4-a716-446655440000
```

## Next Steps

Once the test script works correctly:

1. ✅ Camera initializes successfully
2. ✅ QR codes are detected reliably
3. ✅ QR code data is extracted correctly

You can then integrate the camera into the kiosko application for vehicle retrieval.

## Integration Notes

The camera module will be integrated into:
- `kiosko/app/camera.py` - Camera service class
- `kiosko/app/routes.py` - QR code scanning endpoint
- `kiosko/app/api.py` - API endpoint for QR code validation

## Performance Tips

- **Resolution**: Lower resolution (640x480) is faster for QR detection
- **Frame rate**: Process every 2-3 frames instead of every frame
- **Timeout**: Set timeout for QR detection (don't wait indefinitely)
- **Focus**: Use fixed focus or auto-focus before scanning

