"""Thermal printer service for Cashino KP-300 ticket printing."""
from __future__ import annotations

import logging
import os
import platform
import threading
import time
import uuid
from typing import Optional

try:
    from escpos.printer import Usb, Serial
    from escpos.exceptions import Error as EscposError
    ESCPOS_AVAILABLE = True
except ImportError:
    ESCPOS_AVAILABLE = False
    Usb = None
    Serial = None
    EscposError = Exception


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or fallback


def _is_raspberry_linux() -> bool:
    """Check if running on Linux (Raspberry Pi)."""
    return platform.system() == "Linux"


class PrinterService:
    """Thermal printer service for printing parking tickets.
    
    Supports USB and serial connections with graceful fallback to simulation mode.
    Thread-safe printing operations.
    """
    
    def __init__(
        self,
        vendor_id: Optional[int] = None,
        product_id: Optional[int] = None,
        serial_port: Optional[str] = None,
        baudrate: int = 9600,
        enabled: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.enabled = enabled
        self.logger = logger or logging.getLogger(__name__)
        
        self._lock = threading.Lock()
        self._printer = None
        self._status = "initializing"
        self._status_detail: Optional[str] = None
        self._available = False
        
        if not enabled:
            self._status = "disabled"
            self._status_detail = "Printer disabled via configuration"
            self.logger.info("Printer service disabled")
            return
        
        if not ESCPOS_AVAILABLE:
            self._status = "unavailable"
            self._status_detail = "python-escpos library not installed"
            self.logger.warning("python-escpos not available, printer will run in simulation mode")
            return
        
        # Try to initialize printer
        self._init_printer()
    
    def _init_printer(self) -> None:
        """Initialize printer connection (USB or Serial)."""
        if not ESCPOS_AVAILABLE:
            return
        
        try:
            # Try USB connection first
            if self.vendor_id and self.product_id:
                try:
                    self._printer = Usb(self.vendor_id, self.product_id)
                    self._available = True
                    self._status = "connected"
                    self._status_detail = f"USB (vendor=0x{self.vendor_id:04x}, product=0x{self.product_id:04x})"
                    self.logger.info("Printer connected via USB: %s", self._status_detail)
                    return
                except Exception as e:
                    self.logger.warning("Failed to connect via USB with specified IDs: %s", e)
            
            # Try automatic USB detection (python-escpos can auto-detect)
            if not self.serial_port:
                try:
                    # Try to use Usb() without parameters for auto-detection
                    # This will find the first available USB printer
                    try:
                        self._printer = Usb()
                        self._available = True
                        self._status = "connected"
                        self._status_detail = "USB auto-detected"
                        self.logger.info("Printer connected via USB auto-detection")
                        return
                    except Exception as e:
                        self.logger.debug("USB auto-detection failed: %s", e)
                    
                    # Fallback: Try a few common thermal printer vendor/product IDs
                    # Note: Cashino KP-300 may use different IDs - user should specify via env vars
                    common_ids = [
                        (0x0fe6, 0x811e),  # ICS Advent Parallel Adapter (Cashino KP-300 via adapter)
                        (0x04f9, 0x2016),  # Brother QL-710W
                        (0x04f9, 0x2042),  # Brother QL-820NWB
                        (0x04f9, 0x2043),  # Brother QL-1050
                        (0x04f9, 0x2044),  # Brother QL-1060N
                        (0x04f9, 0x2045),  # Brother QL-1110NWB
                    ]
                    
                    for vid, pid in common_ids:
                        try:
                            self._printer = Usb(vid, pid)
                            self._available = True
                            self._status = "connected"
                            self._status_detail = f"USB auto-detected (vendor=0x{vid:04x}, product=0x{pid:04x})"
                            self.logger.info("Printer connected via USB with common ID: %s", self._status_detail)
                            return
                        except Exception:
                            continue
                    
                    self.logger.warning("No USB printer found with auto-detection or common IDs")
                except Exception as e:
                    self.logger.warning("USB auto-detection failed: %s", e)
            
            # Try serial connection
            if self.serial_port:
                try:
                    self._printer = Serial(devfile=self.serial_port, baudrate=self.baudrate)
                    self._available = True
                    self._status = "connected"
                    self._status_detail = f"Serial ({self.serial_port} @ {self.baudrate} baud)"
                    self.logger.info("Printer connected via serial: %s", self._status_detail)
                    return
                except Exception as e:
                    self.logger.warning("Failed to connect via serial: %s", e)
            
            # Fallback to simulation mode
            self._status = "simulation"
            self._status_detail = "No printer detected, running in simulation mode"
            self.logger.info("Printer running in simulation mode")
            
        except Exception as e:
            self._status = "error"
            self._status_detail = f"Initialization error: {str(e)}"
            self.logger.error("Printer initialization failed: %s", e)
    
    @classmethod
    def from_env(cls, logger: Optional[logging.Logger] = None) -> "PrinterService":
        """Create PrinterService from environment variables."""
        enabled_str = _env("KIOSKO_PRINTER_ENABLED", "true")
        enabled = enabled_str.lower() in ("true", "1", "yes", "on")
        
        vendor_id = None
        product_id = None
        vendor_str = _env("KIOSKO_PRINTER_VENDOR_ID")
        product_str = _env("KIOSKO_PRINTER_PRODUCT_ID")
        if vendor_str and product_str:
            try:
                # Parse hex strings (with or without 0x prefix)
                vendor_id = int(vendor_str, 16) if vendor_str.startswith("0x") else int(vendor_str, 16)
                product_id = int(product_str, 16) if product_str.startswith("0x") else int(product_str, 16)
            except ValueError:
                if logger:
                    logger.warning("Invalid printer vendor/product IDs, using auto-detection")
        
        serial_port = _env("KIOSKO_PRINTER_SERIAL")
        baudrate = int(_env("KIOSKO_PRINTER_BAUDRATE", "9600"))
        
        return cls(
            vendor_id=vendor_id,
            product_id=product_id,
            serial_port=serial_port,
            baudrate=baudrate,
            enabled=enabled,
            logger=logger,
        )
    
    def get_status(self) -> dict:
        """Get printer status information."""
        with self._lock:
            return {
                "available": self._available,
                "status": self._status,
                "status_detail": self._status_detail,
                "enabled": self.enabled,
            }
    
    def _print_simulation(self, content: str) -> None:
        """Simulate printing (for testing without hardware)."""
        self.logger.info("SIMULATION PRINT:\n%s", content)
    
    def _format_entry_ticket(self, vehicle_plate: str, cabin_id: str, timestamp: str, ticket_id: str) -> str:
        """Format entry ticket content."""
        return f"""
================================
    PARKING ENTRY TICKET
================================
Vehicle: {vehicle_plate}
Cabin: {cabin_id}
Entry Time: {timestamp}
Ticket ID: {ticket_id}
================================
"""
    
    def _format_exit_ticket(self, vehicle_plate: str, entry_time: str, exit_time: str, duration: str, cost: str) -> str:
        """Format exit ticket content."""
        return f"""
================================
    PARKING EXIT TICKET
================================
Vehicle: {vehicle_plate}
Entry Time: {entry_time}
Exit Time: {exit_time}
Duration: {duration}
Cost: ${cost}
================================
"""
    
    def print_entry_ticket(self, vehicle_plate: str, cabin_id: str, timestamp: Optional[str] = None, ticket_id: Optional[str] = None) -> bool:
        """Print entry ticket.
        
        Args:
            vehicle_plate: Vehicle license plate
            cabin_id: Cabin identifier
            timestamp: Entry timestamp (ISO format), defaults to current time
            ticket_id: Unique ticket ID, defaults to generated UUID
            
        Returns:
            True if print succeeded (or simulated), False on error
        """
        if not self.enabled:
            self.logger.debug("Printer disabled, skipping entry ticket print")
            return False
        
        if timestamp is None:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if ticket_id is None:
            ticket_id = str(uuid.uuid4())[:8].upper()
        
        content = self._format_entry_ticket(vehicle_plate, cabin_id, timestamp, ticket_id)
        
        with self._lock:
            if not self._available or self._printer is None:
                self._print_simulation(content)
                return True
            
            try:
                # Ensure printer connection is open
                if hasattr(self._printer, 'open'):
                    try:
                        self._printer.open()
                    except Exception:
                        pass  # Already open or doesn't need explicit open
                
                # Print entry ticket
                self._printer.text("\n")
                self._printer.text("PARKING ENTRY TICKET\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text(f"Vehicle: {vehicle_plate}\n")
                self._printer.text(f"Cabin: {cabin_id}\n")
                self._printer.text(f"Entry Time: {timestamp}\n")
                self._printer.text(f"Ticket ID: {ticket_id}\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("\n\n")
                
                # Try to cut paper
                try:
                    self._printer.cut()
                except Exception:
                    self._printer.text("\n\n\n")
                
                # Close connection if needed
                if hasattr(self._printer, 'close'):
                    try:
                        self._printer.close()
                    except Exception:
                        pass
                
                self.logger.info("Entry ticket printed: vehicle=%s, cabin=%s, ticket_id=%s", vehicle_plate, cabin_id, ticket_id)
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing entry ticket: %s", e, exc_info=True)
                self._status = "error"
                self._status_detail = f"Print error: {str(e)}"
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing entry ticket: %s", e, exc_info=True)
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False
    
    def print_exit_ticket(self, vehicle_plate: str, entry_time: str, exit_time: str, duration: str, cost: str) -> bool:
        """Print exit ticket.
        
        Args:
            vehicle_plate: Vehicle license plate
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            duration: Parking duration (formatted string)
            cost: Parking cost (formatted string)
            
        Returns:
            True if print succeeded (or simulated), False on error
        """
        if not self.enabled:
            self.logger.debug("Printer disabled, skipping exit ticket print")
            return False
        
        content = self._format_exit_ticket(vehicle_plate, entry_time, exit_time, duration, cost)
        
        with self._lock:
            if not self._available or self._printer is None:
                self._print_simulation(content)
                return True
            
            try:
                # Ensure printer connection is open
                if hasattr(self._printer, 'open'):
                    try:
                        self._printer.open()
                    except Exception:
                        pass  # Already open or doesn't need explicit open
                
                # Print exit ticket
                self._printer.text("\n")
                self._printer.text("PARKING EXIT TICKET\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text(f"Vehicle: {vehicle_plate}\n")
                self._printer.text(f"Entry Time: {entry_time}\n")
                self._printer.text(f"Exit Time: {exit_time}\n")
                self._printer.text(f"Duration: {duration}\n")
                self._printer.text(f"Cost: ${cost}\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("\n\n")
                
                # Try to cut paper
                try:
                    self._printer.cut()
                except Exception:
                    self._printer.text("\n\n\n")
                
                # Close connection if needed
                if hasattr(self._printer, 'close'):
                    try:
                        self._printer.close()
                    except Exception:
                        pass
                
                self.logger.info("Exit ticket printed: vehicle=%s, cost=%s", vehicle_plate, cost)
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing exit ticket: %s", e, exc_info=True)
                self._status = "error"
                self._status_detail = f"Print error: {str(e)}"
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing exit ticket: %s", e, exc_info=True)
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False
    
    def print_test(self) -> bool:
        """Print a test ticket.
        
        Returns:
            True if print succeeded (or simulated), False on error
        """
        if not self.enabled:
            self.logger.debug("Printer disabled, skipping test print")
            return False
        
        test_content = """
================================
    PRINTER TEST TICKET
================================
This is a test print from
the Kiosko parking system.
Time: {time}
================================
""".format(time=time.strftime("%Y-%m-%d %H:%M:%S"))
        
        with self._lock:
            if not self._available or self._printer is None:
                self._print_simulation(test_content)
                return True
            
            try:
                # Ensure printer connection is open
                if hasattr(self._printer, 'open'):
                    try:
                        self._printer.open()
                    except Exception:
                        pass  # Already open or doesn't need explicit open
                
                # Try simple text first (more compatible)
                self._printer.text("\n")
                self._printer.text("PRINTER TEST TICKET\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("This is a test print from\n")
                self._printer.text("the Kiosko parking system.\n")
                self._printer.text(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("\n\n")
                
                # Try to cut paper (may fail on some printers)
                try:
                    self._printer.cut()
                except Exception as cut_error:
                    self.logger.warning("Paper cut failed (may not be supported): %s", cut_error)
                    # Send line feeds instead
                    self._printer.text("\n\n\n")
                
                # Close connection if needed
                if hasattr(self._printer, 'close'):
                    try:
                        self._printer.close()
                    except Exception:
                        pass
                
                self.logger.info("Test ticket printed successfully")
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing test ticket: %s", e, exc_info=True)
                self._status = "error"
                self._status_detail = f"Print error: {str(e)}"
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing test ticket: %s", e, exc_info=True)
                try:
                    if hasattr(self._printer, 'close'):
                        self._printer.close()
                except Exception:
                    pass
                return False

