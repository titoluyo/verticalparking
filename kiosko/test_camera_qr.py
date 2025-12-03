#!/usr/bin/env python3
"""
Test script for Raspberry Pi camera QR code reading.
Works on both Raspberry Pi (with official camera) and Windows (with webcam).

Usage:
    python test_camera_qr.py

Press 'q' to quit, 's' to save current frame.
"""

import sys
import platform
import time
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
    pass


def detect_camera_backend() -> str:
    """Detect which camera backend to use."""
    if PICAMERA2_AVAILABLE and platform.system() == "Linux":
        # Check if we're on Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'Raspberry Pi' in f.read():
                    return 'picamera2'
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
        self.frame_width = 640
        self.frame_height = 480
        
    def start(self) -> bool:
        """Initialize and start camera."""
        print(f"Using camera backend: {self.backend}")
        
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
        
        # OpenCV backend (USB webcam or fallback)
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                print(f"✗ Failed to open camera {self.camera_index}")
                return False
            
            # Set resolution
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            # Get actual resolution
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"✓ Camera opened (resolution: {actual_width}x{actual_height})")
            return True
        except Exception as e:
            print(f"✗ Failed to open camera: {e}")
            return False
    
    def read_frame(self) -> Optional[Tuple[any, bool]]:
        """Read a frame from camera.
        
        Returns:
            Tuple of (frame, success) or None if error
        """
        if self.backend == 'picamera2' and self.picam2:
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

