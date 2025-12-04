# Video Stream Setup

## Overview

The video streaming feature uses `picamera2` to stream MJPEG video from the Raspberry Pi camera to a web browser. This is based on the [picamera2 MJPEG server example](https://raw.githubusercontent.com/raspberrypi/picamera2/refs/heads/main/examples/mjpeg_server_2.py).

## Prerequisites

- Raspberry Pi with camera module connected
- Raspberry Pi OS (Bullseye or later)
- Python 3.9+

## Installation

### 1. Install System Dependencies

On Raspberry Pi OS, install the required system packages:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera
```

### 2. Install Python Package

The `picamera2` package should be available via apt, but if you need to install via pip:

```bash
pip install picamera2
```

**Note:** It's recommended to use the system package (`python3-picamera2`) rather than pip, as it includes all necessary dependencies.

## Configuration

### Environment Variables

- `KIOSKO_VIDEO_STREAM_ENABLED`: Enable/disable video streaming (default: `true`)

Example:
```bash
export KIOSKO_VIDEO_STREAM_ENABLED=true
```

## Usage

### Access the Video Stream

1. **Web Page**: Navigate to `/video` in your browser
   - Example: `http://localhost:5000/video` or `http://control.local:5000/video`

2. **Direct Stream**: Access the MJPEG stream directly at `/stream.mjpg`
   - This can be embedded in other pages or used with video players that support MJPEG

### Video Stream Details

- **Resolution**: 640x480 pixels
- **Format**: MJPEG (Motion JPEG)
- **Stream Type**: Multipart HTTP stream
- **Frame Rate**: Depends on camera capabilities (typically 30 FPS)

## How It Works

1. The `VideoStreamService` initializes the Raspberry Pi camera using `picamera2`
2. It configures the camera for video capture at 640x480 resolution
3. The MJPEG encoder processes frames and sends them to a `StreamingOutput` buffer
4. The Flask route `/stream.mjpg` serves the stream as a multipart HTTP response
5. The browser displays the stream using an `<img>` tag that continuously updates

## Troubleshooting

### Video Stream Not Available

If you see "Video Stream No Disponible":

1. **Check if running on Raspberry Pi**:
   ```bash
   uname -a  # Should show arm architecture
   ```

2. **Check camera connection**:
   ```bash
   libcamera-hello --list-cameras
   ```

3. **Check picamera2 installation**:
   ```bash
   python3 -c "from picamera2 import Picamera2; print('OK')"
   ```

4. **Check logs**: Look for video stream service initialization messages in the app logs

### Camera Permission Issues

If you get permission errors:

```bash
sudo usermod -a -G video $USER
# Then logout and login again
```

### Performance Issues

- Lower the resolution in `video_stream.py` if needed
- Ensure adequate power supply (Raspberry Pi camera needs good power)
- Check CPU usage: `top` or `htop`

## Integration

The video stream service is automatically initialized when the Flask app starts. It's available via:

- `current_app.config["VIDEO_STREAM_SERVICE"]` in Flask routes
- Status can be checked via `video_service.get_status()`

## Example: Embedding in Other Pages

To embed the video stream in another template:

```html
<img src="{{ url_for('routes.video_stream') }}" alt="Live Video" />
```

## Notes

- Video streaming only works on Linux (Raspberry Pi)
- On Windows or other platforms, the service will initialize but won't be available
- The stream uses hardware MJPEG encoding for better performance
- Multiple clients can connect to the same stream simultaneously

