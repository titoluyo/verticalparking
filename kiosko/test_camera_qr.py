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
import os
import tempfile
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
            # Use rpicam-still in a loop to capture frames continuously
            # This is simpler and more reliable than rpicam-vid with segments
            try:
                # Determine which command to use
                if subprocess.run(['which', 'rpicam-still'], 
                                capture_output=True).returncode == 0:
                    self.libcamera_cmd = 'rpicam-still'
                elif subprocess.run(['which', 'libcamera-still'], 
                                  capture_output=True).returncode == 0:
                    self.libcamera_cmd = 'libcamera-still'
                else:
                    print("✗ rpicam-still or libcamera-still not found")
                    print("  Install with: sudo apt install -y rpicam-apps")
                    print("  Falling back to OpenCV...")
                    self.backend = 'opencv'
                    return False
                
                # Create temporary file for frames
                self.temp_frame_file = tempfile.NamedTemporaryFile(
                    suffix='.jpg', delete=False
                )
                self.temp_frame_file.close()
                self.frame_path = self.temp_frame_file.name
                self.last_capture_time = 0
                self.capture_interval = 0.1  # Capture every 100ms (10 FPS)
                
                # Test capture to verify camera works
                test_result = subprocess.run(
                    [
                        self.libcamera_cmd,
                        '--width', str(self.frame_width),
                        '--height', str(self.frame_height),
                        '--output', self.frame_path,
                        '--nopreview',
                        '--timeout', '1000',  # 1 second timeout
                    ],
                    capture_output=True,
                    timeout=2
                )
                
                if test_result.returncode == 0 and os.path.exists(self.frame_path) and os.path.getsize(self.frame_path) > 0:
                    print(f"✓ Raspberry Pi camera initialized via {self.libcamera_cmd}")
                    print(f"  Will capture frames at ~{1/self.capture_interval:.1f} FPS")
                    return True
                else:
                    stderr = test_result.stderr.decode() if test_result.stderr else ""
                    print(f"✗ Failed to test camera capture")
                    if stderr:
                        print(f"  Error: {stderr[:200]}")
                    print("  Falling back to OpenCV...")
                    self.backend = 'opencv'
                    return False
                    
            except Exception as e:
                print(f"✗ Failed to initialize libcamera: {e}")
                import traceback
                traceback.print_exc()
                print("  Falling back to OpenCV...")
                self.backend = 'opencv'
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
            
            # If index-based failed, try direct device paths
            # On Raspberry Pi, try ISP devices first (video13, video14) as they're more likely to work
            if not camera_opened and video_devices:
                print("Trying direct device paths...")
                # Prioritize ISP devices (video13, video14) which are more likely to work
                prioritized_devices = []
                other_devices = []
                for idx, dev_path in video_devices:
                    if 'video13' in dev_path or 'video14' in dev_path:
                        prioritized_devices.append((idx, dev_path))
                    else:
                        other_devices.append((idx, dev_path))
                
                # Try prioritized devices first, then others
                for idx, dev_path in prioritized_devices + other_devices:
                    try:
                        self.camera = cv2.VideoCapture(dev_path)
                        if self.camera.isOpened():
                            # Set buffer size to reduce latency
                            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
        if self.backend == 'libcamera' and hasattr(self, 'libcamera_cmd'):
            try:
                # Capture a new frame if enough time has passed
                current_time = time.time()
                if current_time - self.last_capture_time >= self.capture_interval:
                    # Capture new frame (non-blocking with short timeout)
                    result = subprocess.run(
                        [
                            self.libcamera_cmd,
                            '--width', str(self.frame_width),
                            '--height', str(self.frame_height),
                            '--output', self.frame_path,
                            '--nopreview',
                            '--timeout', '100',  # 100ms timeout for faster capture
                        ],
                        capture_output=True,
                        timeout=0.5
                    )
                    
                    if result.returncode == 0:
                        self.last_capture_time = current_time
                    # If capture failed, we'll try to read the last frame
                
                # Read the frame file
                if os.path.exists(self.frame_path):
                    file_size = os.path.getsize(self.frame_path)
                    if file_size > 0:
                        # Read the image
                        frame = cv2.imread(self.frame_path)
                        if frame is not None and frame.size > 0:
                            return (frame, True)
                return None
            except Exception as e:
                # Silently fail and return None - will retry next frame
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
        # Clean up temp file
        if hasattr(self, 'temp_frame_file'):
            try:
                os.unlink(self.temp_frame_file.name)
            except:
                pass
        
        # No process to kill for rpicam-still approach (each capture is separate)
        
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
    
    print("\nCamera ready! Scanning for QR codes...")
    print("Press Ctrl+C to stop\n")
    
    frame_count = 0
    last_qr_data = None
    last_qr_time = 0
    last_frame_time = time.time()
    last_status_time = time.time()
    
    # Check if we have a display (for GUI)
    has_display = os.getenv('DISPLAY') is not None
    if not has_display:
        print("ℹ No display available - running in console mode")
        print("  QR codes will be printed to console when detected\n")
    
    try:
        while True:
            result = reader.read_frame()
            
            if result is None:
                # For libcamera backend, None is OK - just means no new frame yet
                time.sleep(0.05)
                continue
            
            frame, success = result
            if not success or frame is None:
                time.sleep(0.05)
                continue
            
            frame_count += 1
            current_time = time.time()
            fps = 1.0 / (current_time - last_frame_time) if current_time > last_frame_time else 0
            last_frame_time = current_time
            
            # Detect QR codes
            qr_codes = reader.detect_qr_codes(frame)
            
            # Display QR code data if found
            if qr_codes:
                for qr in qr_codes:
                    qr_data = qr['data']
                    
                    # Only print if it's a new QR code or 2 seconds have passed
                    if qr_data != last_qr_data or (current_time - last_qr_time) > 2:
                        print(f"✓ QR Code detected: {qr_data}")
                        last_qr_data = qr_data
                        last_qr_time = current_time
                
                # Draw overlay if we have display
                if has_display:
                    reader.draw_qr_overlay(frame, qr_codes)
            else:
                # Show "No QR code" message if we have display
                if has_display:
                    cv2.putText(frame, "No QR code detected", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Show status in console every 5 seconds
            if current_time - last_status_time > 5:
                print(f"  Scanning... Frame: {frame_count}, FPS: {fps:.1f}")
                last_status_time = current_time
            
            # Display frame if we have display
            if has_display:
                # Show frame info
                info_text = f"Frame: {frame_count} | FPS: {fps:.1f} | Backend: {reader.backend}"
                cv2.putText(frame, info_text, (10, frame.shape[0] - 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, "Press 'q' or ESC to quit | 's' to save", (10, frame.shape[0] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Display frame
                cv2.imshow('QR Code Reader', frame)
                
                # Check for keyboard input
                key = cv2.waitKey(30) & 0xFF
                if key == ord('q') or key == 27:  # 'q' or ESC
                    print("\nQuitting...")
                    break
                elif key == ord('s'):
                    filename = f"qr_frame_{int(time.time())}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"✓ Frame saved: {filename}")
            else:
                # No display - just process frames and print QR codes
                # Small delay to prevent CPU spinning
                time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("\nStopping camera...")
        reader.stop()
        print("Done!")


if __name__ == "__main__":
    main()

