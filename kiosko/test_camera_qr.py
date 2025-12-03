#!/usr/bin/env python3
"""
Test script for Raspberry Pi camera QR code reading.
Works on both Raspberry Pi (with official camera via OpenCV/V4L2) and Windows (with webcam).

The script uses OpenCV which can access the Raspberry Pi camera directly via V4L2.
No need for picamera2 - it's optional and has build dependencies.

Usage:
    python test_camera_qr.py

Press 'q' to quit, 's' to save current frame.
"""

import sys
import platform
import time
import subprocess
import numpy as np
from typing import Optional, Tuple

# Try to import camera libraries
try:
    import cv2
except ImportError:
    print("ERROR: opencv-python not installed. Install with:")
    print("  pip install opencv-python")
    sys.exit(1)

try:
    from pyzbar import pyzbar
except ImportError:
    print("ERROR: pyzbar not installed. Install with:")
    print("  pip install pyzbar")
    print("On Linux/Raspberry Pi, also install: sudo apt-get install libzbar0")
    sys.exit(1)

# Try to import picamera2 (Raspberry Pi only)
PICAMERA2_AVAILABLE = False
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    # Not on Raspberry Pi or picamera2 not installed
    # This is OK - will fall back to OpenCV
    pass
except Exception as e:
    # picamera2 installed but not working (e.g., missing system dependencies)
    print(f"Warning: picamera2 import failed: {e}")
    print("  Will fall back to OpenCV. Install system dependencies:")
    print("  sudo apt install -y libcap-dev python3-dev build-essential")
    pass


def detect_camera_backend() -> str:
    """Detect which camera backend to use."""
    # On Raspberry Pi with libcamera, we need to use libcamera-vid/rpicam-vid
    # to capture frames, then process with OpenCV
    if platform.system() == "Linux":
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'Raspberry Pi' in f.read():
                    # Check if rpicam-vid or libcamera-vid is available
                    if subprocess.run(['which', 'rpicam-vid'], 
                                    capture_output=True).returncode == 0:
                        return 'libcamera'
                    elif subprocess.run(['which', 'libcamera-vid'], 
                                      capture_output=True).returncode == 0:
                        return 'libcamera'
        except:
            pass
    
    # Fallback to OpenCV (works on Windows and Linux with USB cameras)
    return 'opencv'


class CameraQRReader:
    """QR code reader using camera."""
    
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.backend = detect_camera_backend()
        self.camera = None
        self.picam2 = None
        self.libcamera_process = None
        self.frame_width = 640
        self.frame_height = 480
        
    def start(self) -> bool:
        """Initialize and start camera."""
        print(f"Using camera backend: {self.backend}")
        
        if self.backend == 'libcamera':
            # Use rpicam-vid to capture frames via stdout
            # OpenCV can read MJPEG stream from stdout
            try:
                # Determine which command to use
                if subprocess.run(['which', 'rpicam-vid'], 
                                capture_output=True).returncode == 0:
                    cmd = 'rpicam-vid'
                elif subprocess.run(['which', 'libcamera-vid'], 
                                  capture_output=True).returncode == 0:
                    cmd = 'libcamera-vid'
                else:
                    print("✗ rpicam-vid or libcamera-vid not found")
                    print("  Install with: sudo apt install -y rpicam-apps")
                    self.backend = 'opencv'
                    return False
                
                # Start libcamera process to capture frames to stdout as MJPEG
                self.libcamera_process = subprocess.Popen(
                    [
                        cmd,
                        '--width', str(self.frame_width),
                        '--height', str(self.frame_height),
                        '--timeout', '0',  # Continuous
                        '--output', '-',  # stdout
                        '--nopreview',
                        '--codec', 'mjpeg',
                        '--inline',  # Include headers in output
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # Unbuffered
                )
                
                # Give it a moment to start
                time.sleep(0.5)
                
                # Check if process is still running
                if self.libcamera_process.poll() is None:
                    # Create VideoCapture from pipe
                    # We'll read raw bytes and decode MJPEG frames
                    print(f"✓ Raspberry Pi camera initialized via {cmd}")
                    self.libcamera_stdout = self.libcamera_process.stdout
                    return True
                else:
                    stderr_output = self.libcamera_process.stderr.read().decode()
                    print(f"✗ Failed to start {cmd}")
                    print(f"  Error: {stderr_output}")
                    self.stop()
                    self.backend = 'opencv'
                    return False
                    
            except Exception as e:
                print(f"✗ Failed to initialize libcamera: {e}")
                print("  Falling back to OpenCV...")
                self.backend = 'opencv'
                if hasattr(self, 'libcamera_process') and self.libcamera_process:
                    self.stop()
                return False
        
        if self.backend == 'picamera2':
            try:
                self.picam2 = Picamera2()
                # Configure for preview (lower resolution for speed)
                preview_config = self.picam2.create_preview_configuration(
                    main={"size": (self.frame_width, self.frame_height)}
                )
                self.picam2.configure(preview_config)
                self.picam2.start()
                print("✓ Raspberry Pi camera initialized")
                return True
            except Exception as e:
                print(f"✗ Failed to initialize Raspberry Pi camera: {e}")
                print("  Falling back to OpenCV...")
                self.backend = 'opencv'
        
        # OpenCV backend (works with Raspberry Pi camera via V4L2)
        # On Raspberry Pi, the camera appears as /dev/video0 or /dev/video1
        try:
            # First, try to find available video devices
            import os
            video_devices = []
            for i in range(10):
                dev_path = f"/dev/video{i}"
                if os.path.exists(dev_path):
                    video_devices.append((i, dev_path))
            
            if video_devices:
                print(f"Found video devices: {[f'{idx} ({path})' for idx, path in video_devices]}")
            else:
                print("No /dev/video* devices found")
                print("  Trying default camera indices anyway...")
            
            # Try different camera indices (0, 1, etc.)
            camera_opened = False
            for idx in range(5):  # Try indices 0-4
                try:
                    # Try opening with index
                    self.camera = cv2.VideoCapture(idx)
                    if self.camera.isOpened():
                        # Test if we can read a frame (with timeout)
                        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer
                        ret, test_frame = self.camera.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            self.camera_index = idx
                            camera_opened = True
                            break
                        else:
                            self.camera.release()
                            self.camera = None
                except Exception as e:
                    if self.camera:
                        self.camera.release()
                        self.camera = None
                    continue
            
            # If index-based failed, try direct device path
            if not camera_opened and video_devices:
                print("Trying direct device paths...")
                for idx, dev_path in video_devices:
                    try:
                        self.camera = cv2.VideoCapture(dev_path)
                        if self.camera.isOpened():
                            ret, test_frame = self.camera.read()
                            if ret and test_frame is not None and test_frame.size > 0:
                                self.camera_index = dev_path
                                camera_opened = True
                                print(f"✓ Opened camera via direct path: {dev_path}")
                                break
                            else:
                                self.camera.release()
                                self.camera = None
                    except Exception as e:
                        if self.camera:
                            self.camera.release()
                            self.camera = None
                        continue
            
            if not camera_opened:
                print(f"✗ Failed to open camera")
                print("  Tried indices 0-4 and direct device paths")
                print("  Make sure camera is connected and accessible")
                print("  On Raspberry Pi, check with: ls -l /dev/video*")
                print("  Test camera with: rpicam-hello")
                return False
            
            # Set resolution (may not work on all cameras, but try anyway)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            
            # Get actual resolution
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"✓ Camera opened (index: {self.camera_index}, resolution: {actual_width}x{actual_height})")
            return True
        except Exception as e:
            print(f"✗ Failed to open camera: {e}")
            return False
    
    def read_frame(self) -> Optional[Tuple[any, bool]]:
        """Read a frame from camera.
        
        Returns:
            Tuple of (frame, success) or None if error
        """
        if self.backend == 'libcamera' and self.libcamera_process:
            try:
                # Read MJPEG stream from stdout
                # MJPEG frames start with FF D8 and end with FF D9
                if not hasattr(self, 'libcamera_buffer'):
                    self.libcamera_buffer = bytearray()
                
                # Read available data
                data = self.libcamera_stdout.read(8192)
                if not data:
                    return None
                
                self.libcamera_buffer.extend(data)
                
                # Find JPEG frame markers
                start_marker = b'\xff\xd8'
                end_marker = b'\xff\xd9'
                
                start_idx = self.libcamera_buffer.find(start_marker)
                if start_idx == -1:
                    return None
                
                # Remove data before start marker
                if start_idx > 0:
                    self.libcamera_buffer = self.libcamera_buffer[start_idx:]
                
                # Find end marker
                end_idx = self.libcamera_buffer.find(end_marker, 2)
                if end_idx == -1:
                    return None  # Need more data
                
                # Extract frame
                frame_data = bytes(self.libcamera_buffer[:end_idx + 2])
                self.libcamera_buffer = self.libcamera_buffer[end_idx + 2:]
                
                # Decode JPEG
                frame_array = np.frombuffer(frame_data, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                
                if frame is not None and frame.size > 0:
                    return (frame, True)
                return None
            except Exception as e:
                return None
        elif self.backend == 'picamera2' and self.picam2:
            try:
                frame = self.picam2.capture_array()
                # Convert RGB to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return (frame, True)
            except Exception as e:
                print(f"Error reading from picamera2: {e}")
                return None
        else:
            if self.camera is None:
                return None
            ret, frame = self.camera.read()
            return (frame, ret) if ret else None
    
    def detect_qr_codes(self, frame) -> list:
        """Detect QR codes in frame.
        
        Args:
            frame: OpenCV image frame
            
        Returns:
            List of detected QR codes with data and position
        """
        # Convert to grayscale for QR detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect QR codes
        qr_codes = pyzbar.decode(gray)
        
        results = []
        for qr in qr_codes:
            data = qr.data.decode('utf-8')
            rect = qr.rect
            results.append({
                'data': data,
                'rect': (rect.left, rect.top, rect.width, rect.height),
                'polygon': qr.polygon
            })
        
        return results
    
    def draw_qr_overlay(self, frame, qr_codes: list) -> None:
        """Draw QR code detection overlay on frame."""
        for qr in qr_codes:
            # Draw rectangle
            x, y, w, h = qr['rect']
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Draw polygon if available
            if qr['polygon']:
                points = [(p.x, p.y) for p in qr['polygon']]
                for i in range(len(points)):
                    cv2.line(frame, points[i], points[(i + 1) % len(points)], (0, 255, 0), 2)
            
            # Draw text
            text = qr['data']
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (x, y - text_size[1] - 10), 
                        (x + text_size[0], y), (0, 255, 0), -1)
            cv2.putText(frame, text, (x, y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    def stop(self) -> None:
        """Stop and release camera."""
        if self.libcamera_process:
            try:
                self.libcamera_process.terminate()
                try:
                    self.libcamera_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.libcamera_process.kill()
                    self.libcamera_process.wait()
            except:
                try:
                    self.libcamera_process.kill()
                except:
                    pass
            # Close stdout
            if hasattr(self, 'libcamera_stdout'):
                try:
                    self.libcamera_stdout.close()
                except:
                    pass
        
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
        
        if self.camera:
            self.camera.release()
        
        cv2.destroyAllWindows()


def main():
    """Main test loop."""
    print("=" * 60)
    print("Camera QR Code Reader Test")
    print("=" * 60)
    print("\nControls:")
    print("  'q' - Quit")
    print("  's' - Save current frame")
    print("\nStarting camera...")
    
    reader = CameraQRReader()
    
    if not reader.start():
        print("\n✗ Failed to start camera. Exiting.")
        return
    
    print("\nCamera ready! Point QR code at camera...")
    print("Press 'q' to quit\n")
    
    frame_count = 0
    last_qr_data = None
    last_qr_time = 0
    
    try:
        while True:
            result = reader.read_frame()
            if result is None:
                print("Failed to read frame")
                break
            
            frame, success = result
            if not success:
                continue
            
            frame_count += 1
            
            # Detect QR codes
            qr_codes = reader.detect_qr_codes(frame)
            
            # Display QR code data if found
            if qr_codes:
                for qr in qr_codes:
                    qr_data = qr['data']
                    current_time = time.time()
                    
                    # Only print if it's a new QR code or 2 seconds have passed
                    if qr_data != last_qr_data or (current_time - last_qr_time) > 2:
                        print(f"✓ QR Code detected: {qr_data}")
                        last_qr_data = qr_data
                        last_qr_time = current_time
                
                # Draw overlay
                reader.draw_qr_overlay(frame, qr_codes)
            else:
                # Show "No QR code" message
                cv2.putText(frame, "No QR code detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Show frame info
            info_text = f"Frame: {frame_count} | Backend: {reader.backend}"
            cv2.putText(frame, info_text, (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display frame
            cv2.imshow('QR Code Reader', frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                filename = f"qr_frame_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                print(f"✓ Frame saved: {filename}")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("\nStopping camera...")
        reader.stop()
        print("Done!")


if __name__ == "__main__":
    main()

