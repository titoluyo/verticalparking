"""
Video streaming service using picamera2 for MJPEG streaming.
Based on: https://raw.githubusercontent.com/raspberrypi/picamera2/refs/heads/main/examples/mjpeg_server_2.py

This uses the hardware MJPEG encoder for efficient streaming on Raspberry Pi.
"""
import io
import logging
import platform
from threading import Condition
from typing import Optional

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None
    MJPEGEncoder = None
    FileOutput = None


class StreamingOutput(io.BufferedIOBase):
    """Output handler for MJPEG streaming."""
    
    def __init__(self):
        self.frame = None
        self.condition = Condition()
    
    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class VideoStreamService:
    """Service for video streaming using picamera2 hardware MJPEG encoder."""
    
    def __init__(self, logger: Optional[logging.Logger] = None, enabled: bool = True):
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = enabled
        self._picam2 = None
        self._output = None
        self._available = False
        self._width = 640
        self._height = 480
        
        if not enabled:
            self.logger.info("Video stream service disabled")
            return
        
        if not PICAMERA2_AVAILABLE:
            self.logger.warning("picamera2 not available - video streaming will not work")
            return
        
        # Only initialize on Linux (Raspberry Pi)
        if platform.system() != "Linux":
            self.logger.info("Video streaming only available on Linux (Raspberry Pi)")
            return
        
        self._init_camera()
    
    def _init_camera(self) -> bool:
        """Initialize the camera using picamera2."""
        try:
            self._picam2 = Picamera2()
            self._picam2.configure(
                self._picam2.create_video_configuration(
                    main={"size": (self._width, self._height)}
                )
            )
            self._output = StreamingOutput()
            self._picam2.start_recording(MJPEGEncoder(), FileOutput(self._output))
            self._available = True
            self.logger.info(f"Video stream initialized: {self._width}x{self._height}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize video stream: {e}", exc_info=True)
            self._available = False
            return False
    
    @classmethod
    def from_env(cls, logger: Optional[logging.Logger] = None) -> "VideoStreamService":
        """Create VideoStreamService from environment variables."""
        import os
        enabled = os.getenv("KIOSKO_VIDEO_STREAM_ENABLED", "true").lower() == "true"
        return cls(logger=logger, enabled=enabled)
    
    def get_output(self) -> Optional[StreamingOutput]:
        """Get the streaming output object."""
        return self._output if self._available else None
    
    def is_available(self) -> bool:
        """Check if video streaming is available."""
        return self._available
    
    def get_status(self) -> dict:
        """Get video stream status."""
        return {
            "available": self._available,
            "enabled": self.enabled,
            "resolution": f"{self._width}x{self._height}" if self._available else None
        }
    
    def stop(self) -> None:
        """Stop video streaming."""
        if self._picam2 and self._available:
            try:
                self._picam2.stop_recording()
                self.logger.info("Video stream stopped")
            except Exception as e:
                self.logger.error(f"Error stopping video stream: {e}")
            finally:
                self._available = False
                self._picam2 = None
                self._output = None
