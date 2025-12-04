"""
QR code detection service using pyzbar and Pillow.
Works with images from picamera2 video stream.
"""
import logging
from typing import Optional, List, Dict
from io import BytesIO

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    pyzbar = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None


class QRDetector:
    """Service for detecting QR codes in images."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        if not PYZBAR_AVAILABLE:
            self.logger.warning("pyzbar not available - QR detection will not work")
        if not PIL_AVAILABLE:
            self.logger.warning("PIL/Pillow not available - QR detection will not work")
    
    def detect_from_bytes(self, image_bytes: bytes) -> List[Dict]:
        """Detect QR codes from image bytes (JPEG, PNG, etc.).
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            List of QR code dictionaries with 'data', 'rect', 'polygon' keys
        """
        if not PYZBAR_AVAILABLE or not PIL_AVAILABLE:
            return []
        
        try:
            # Load image from bytes
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if needed (pyzbar works with RGB)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Detect QR codes
            qr_codes = pyzbar.decode(image)
            
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
                    'polygon': polygon,
                    'type': qr.type
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error detecting QR codes: {e}")
            return []
    
    def detect_from_pil_image(self, image: Image.Image) -> List[Dict]:
        """Detect QR codes from a PIL Image.
        
        Args:
            image: PIL Image object
            
        Returns:
            List of QR code dictionaries with 'data', 'rect', 'polygon' keys
        """
        if not PYZBAR_AVAILABLE or not PIL_AVAILABLE:
            return []
        
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Detect QR codes
            qr_codes = pyzbar.decode(image)
            
            result = []
            for qr in qr_codes:
                qr_data = qr.data.decode('utf-8')
                rect = qr.rect
                polygon = qr.polygon if hasattr(qr, 'polygon') else None
                
                result.append({
                    'data': qr_data,
                    'rect': (rect.left, rect.top, rect.width, rect.height),
                    'polygon': polygon,
                    'type': qr.type
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error detecting QR codes: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if QR detection is available."""
        return PYZBAR_AVAILABLE and PIL_AVAILABLE

