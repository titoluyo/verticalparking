"""
Camera service for QR code detection and video streaming.
Supports Raspberry Pi camera via libcamera tools and OpenCV.
"""
import os
import platform
import subprocess
import tempfile
import time
import logging
from typing import Optional, Tuple, List, Dict
from threading import Lock

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


class CameraService:
    """Service for camera access and QR code detection."""
    
    def __init__(self, logger: Optional[logging.Logger] = None, enabled: bool = True):
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = enabled
        self._lock = Lock()
        self._camera = None
        self._backend = None
        self._libcamera_cmd = None
        self._frame_path = None
        self._last_capture_time = 0
        self._capture_interval = 0.1  # 100ms = ~10 FPS
        self.frame_width = 640
        self.frame_height = 480
        self._available = False
        
        if not enabled:
            self.logger.info("Camera service disabled")
            return
        
        if not CV2_AVAILABLE:
            self.logger.warning("opencv-python not available - camera service will not work")
            return
        
        if not PYZBAR_AVAILABLE:
            self.logger.warning("pyzbar not available - QR detection will not work")
            return
        
        # Detect backend
        self._backend = self._detect_backend()
        self.logger.info(f"Camera service initialized with backend: {self._backend}")
    
    @classmethod
    def from_env(cls, logger: Optional[logging.Logger] = None) -> "CameraService":
        """Create CameraService from environment variables."""
        enabled = os.getenv("KIOSKO_CAMERA_ENABLED", "true").lower() == "true"
        return cls(logger=logger, enabled=enabled)
    
    def _detect_backend(self) -> str:
        """Detect which camera backend to use."""
        if platform.system() == "Linux":
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    if 'Raspberry Pi' in f.read():
                        # Check if rpicam-still or libcamera-still is available
                        if subprocess.run(['which', 'rpicam-still'], 
                                        capture_output=True).returncode == 0:
                            return 'libcamera'
                        elif subprocess.run(['which', 'libcamera-still'], 
                                          capture_output=True).returncode == 0:
                            return 'libcamera'
            except:
                pass
        
        # Fallback to OpenCV
        return 'opencv'
    
    def start(self) -> bool:
        """Initialize and start camera."""
        if not self.enabled:
            return False
        
        with self._lock:
            if self._available:
                return True
            
            if self._backend == 'libcamera':
                return self._start_libcamera()
            else:
                return self._start_opencv()
    
    def _start_libcamera(self) -> bool:
        """Start camera using libcamera tools (rpicam-still)."""
        try:
            # Determine which command to use
            if subprocess.run(['which', 'rpicam-still'], 
                            capture_output=True).returncode == 0:
                self._libcamera_cmd = 'rpicam-still'
            elif subprocess.run(['which', 'libcamera-still'], 
                              capture_output=True).returncode == 0:
                self._libcamera_cmd = 'libcamera-still'
            else:
                self.logger.warning("rpicam-still not found, falling back to OpenCV")
                self._backend = 'opencv'
                return self._start_opencv()
            
            # Create temporary file for frames
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_file.close()
            self._frame_path = temp_file.name
            self._last_capture_time = 0
            
            # Test capture
            test_result = subprocess.run(
                [
                    self._libcamera_cmd,
                    '--width', str(self.frame_width),
                    '--height', str(self.frame_height),
                    '--output', self._frame_path,
                    '--nopreview',
                    '--timeout', '1000',
                ],
                capture_output=True,
                timeout=2
            )
            
            if test_result.returncode == 0 and os.path.exists(self._frame_path) and os.path.getsize(self._frame_path) > 0:
                self._available = True
                self.logger.info(f"Camera initialized via {self._libcamera_cmd}")
                return True
            else:
                self.logger.warning("Failed to test camera capture, falling back to OpenCV")
                self._backend = 'opencv'
                return self._start_opencv()
                
        except Exception as e:
            self.logger.warning(f"Failed to initialize libcamera: {e}, falling back to OpenCV")
            self._backend = 'opencv'
            return self._start_opencv()
    
    def _start_opencv(self) -> bool:
        """Start camera using OpenCV."""
        try:
            # Try different camera indices
            for idx in range(5):
                try:
                    camera = cv2.VideoCapture(idx)
                    if camera.isOpened():
                        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        ret, test_frame = camera.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                            self._camera = camera
                            self._available = True
                            self.logger.info(f"Camera opened via OpenCV (index: {idx})")
                            return True
                        else:
                            camera.release()
                except:
                    continue
            
            self.logger.warning("Failed to open camera with OpenCV")
            return False
        except Exception as e:
            self.logger.error(f"Error starting OpenCV camera: {e}")
            return False
    
    def read_frame(self) -> Optional[Tuple[any, bool]]:
        """Read a frame from camera.
        
        Returns:
            Tuple of (frame, success) or None if error
        """
        if not self._available:
            return None
        
        with self._lock:
            if self._backend == 'libcamera' and self._libcamera_cmd:
                try:
                    current_time = time.time()
                    if current_time - self._last_capture_time >= self._capture_interval:
                        result = subprocess.run(
                            [
                                self._libcamera_cmd,
                                '--width', str(self.frame_width),
                                '--height', str(self.frame_height),
                                '--output', self._frame_path,
                                '--nopreview',
                                '--timeout', '100',
                            ],
                            capture_output=True,
                            timeout=0.5
                        )
                        if result.returncode == 0:
                            self._last_capture_time = current_time
                    
                    if os.path.exists(self._frame_path):
                        file_size = os.path.getsize(self._frame_path)
                        if file_size > 0:
                            frame = cv2.imread(self._frame_path)
                            if frame is not None and frame.size > 0:
                                return (frame, True)
                    return None
                except:
                    return None
            else:
                if self._camera is None:
                    return None
                ret, frame = self._camera.read()
                return (frame, ret) if ret else None
    
    def detect_qr_codes(self, frame) -> List[Dict]:
        """Detect QR codes in frame.
        
        Args:
            frame: OpenCV image frame
            
        Returns:
            List of QR code dictionaries with 'data', 'rect', 'polygon' keys
        """
        if not PYZBAR_AVAILABLE:
            return []
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect QR codes
            qr_codes = pyzbar.decode(gray)
            
            result = []
            for qr in qr_codes:
                # Extract data
                qr_data = qr.data.decode('utf-8')
                
                # Get bounding rect
                rect = qr.rect
                
                # Get polygon points
                polygon = qr.polygon if hasattr(qr, 'polygon') else None
                
                result.append({
                    'data': qr_data,
                    'rect': (rect.left, rect.top, rect.width, rect.height),
                    'polygon': polygon
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error detecting QR codes: {e}")
            return []
    
    def get_status(self) -> Dict:
        """Get camera service status."""
        return {
            "available": self._available,
            "enabled": self.enabled,
            "backend": self._backend,
            "resolution": f"{self.frame_width}x{self.frame_height}" if self._available else None
        }
    
    def stop(self) -> None:
        """Stop and release camera."""
        with self._lock:
            if self._camera:
                self._camera.release()
                self._camera = None
            
            if self._frame_path and os.path.exists(self._frame_path):
                try:
                    os.unlink(self._frame_path)
                except:
                    pass
                self._frame_path = None
            
            self._available = False

