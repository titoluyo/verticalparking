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
    
    def _check_connection(self) -> bool:
        """Check if printer connection is healthy and reconnect if needed.
        
        This method performs a lightweight check. If the connection appears broken,
        it attempts to reconnect. Actual connection health is validated during
        print operations, which will trigger reconnection on errors.
        
        Returns:
            True if connection is available, False otherwise
        """
        if not ESCPOS_AVAILABLE:
            return False
        
        if self._printer is None:
            # Try to reconnect if we had a printer before
            return self._reconnect()
        
        # For USB printers, verify device is still accessible
        try:
            if hasattr(self._printer, 'device'):
                # Access device property - this will raise an exception if disconnected
                # We use a simple attribute access as a health check
                _ = self._printer.device
            # For serial printers, assume connection is stable
            # (serial connections are typically more reliable)
            return True
        except (AttributeError, Exception) as e:
            # Connection appears broken, attempt to reconnect
            self.logger.debug("Printer connection check failed, attempting to reconnect: %s", e)
            return self._reconnect()
    
    def _reconnect(self) -> bool:
        """Reconnect to printer after connection loss.
        
        Returns:
            True if reconnection succeeded, False otherwise
        """
        if not ESCPOS_AVAILABLE:
            return False
        
        # Close existing connection if it exists
        if self._printer is not None:
            try:
                if hasattr(self._printer, 'close'):
                    self._printer.close()
            except Exception:
                pass  # Ignore errors when closing broken connection
            self._printer = None
        
        # Reset status
        self._available = False
        self._status = "reconnecting"
        self._status_detail = "Attempting to reconnect to printer"
        
        # Try to reconnect using the same method as initialization
        try:
            # Try USB connection first (with saved IDs)
            if self.vendor_id and self.product_id:
                try:
                    self._printer = Usb(self.vendor_id, self.product_id)
                    self._available = True
                    self._status = "connected"
                    self._status_detail = f"USB (vendor=0x{self.vendor_id:04x}, product=0x{self.product_id:04x})"
                    self.logger.info("Printer reconnected via USB: %s", self._status_detail)
                    return True
                except Exception as e:
                    self.logger.debug("Reconnection via USB with specified IDs failed: %s", e)
            
            # Try automatic USB detection
            if not self.serial_port:
                try:
                    # Try auto-detection
                    try:
                        self._printer = Usb()
                        self._available = True
                        self._status = "connected"
                        self._status_detail = "USB auto-detected"
                        self.logger.info("Printer reconnected via USB auto-detection")
                        return True
                    except Exception:
                        pass
                    
                    # Try common IDs
                    common_ids = [
                        (0x0fe6, 0x811e),  # ICS Advent Parallel Adapter
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
                            self.logger.info("Printer reconnected via USB with common ID: %s", self._status_detail)
                            return True
                        except Exception:
                            continue
                except Exception:
                    pass
            
            # Try serial connection
            if self.serial_port:
                try:
                    self._printer = Serial(devfile=self.serial_port, baudrate=self.baudrate)
                    self._available = True
                    self._status = "connected"
                    self._status_detail = f"Serial ({self.serial_port} @ {self.baudrate} baud)"
                    self.logger.info("Printer reconnected via serial: %s", self._status_detail)
                    return True
                except Exception as e:
                    self.logger.debug("Reconnection via serial failed: %s", e)
            
            # Reconnection failed
            self._status = "disconnected"
            self._status_detail = "Printer disconnected, reconnection failed"
            self.logger.warning("Printer reconnection failed, will retry on next print")
            return False
            
        except Exception as e:
            self._status = "error"
            self._status_detail = f"Reconnection error: {str(e)}"
            self.logger.error("Printer reconnection error: %s", e)
            return False
    
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
            vehicle_plate: Vehicle license plate (not used in current design, kept for API compatibility)
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
        
        # Split timestamp into date and time
        entry_date = timestamp[:10] if len(timestamp) >= 10 else timestamp
        entry_hour = timestamp[11:19] if len(timestamp) >= 19 else ""
        
        # QR code data (without vehicle plate for now)
        qr_data = f"PARKING:{ticket_id}"
        
        # Use 24 characters width for 80mm paper (safe width)
        WIDTH = 24
        
        content = self._format_entry_ticket(vehicle_plate, cabin_id, timestamp, ticket_id)
        
        with self._lock:
            if not self._available or self._printer is None:
                self._print_simulation(content)
                return True
            
            # Check connection health and reconnect if needed
            if not self._check_connection():
                self.logger.warning("Printer connection unavailable, using simulation mode")
                self._print_simulation(content)
                return True
            
            try:
                # Set encoding to CP850 for Spanish character support
                try:
                    self._printer.charcode("CP850")
                except Exception:
                    pass  # Continue if encoding fails
                
                # Print entry ticket - Corporate with Boxes design
                p = self._printer
                p.text("\n\n")
                p.set(align="center", bold=True, double_width=True)
                p.text("VERTICAL PARKING\n")
                p.set(align="center", bold=True, double_width=False)
                p.text("Estacionamiento\n")
                p.text("=" * WIDTH + "\n")
                p.set(align="left", bold=False)
                p.text("+" + "-" * (WIDTH - 2) + "+\n")
                p.text("| TICKET DE INGRESO" + " " * (WIDTH - 20) + "|\n")
                p.text("+" + "-" * (WIDTH - 2) + "+\n")
                p.text(f"| Espacio:  {cabin_id:<{WIDTH-13}} |\n")
                p.text(f"| Fecha:    {entry_date:<{WIDTH-13}} |\n")
                p.text(f"| Hora:     {entry_hour:<{WIDTH-13}} |\n")
                p.text(f"| Ticket:   {ticket_id:<{WIDTH-13}} |\n")
                p.text("+" + "-" * (WIDTH - 2) + "+\n")
                p.text("=" * WIDTH + "\n")
                p.set(align="center")
                p.text("CÓDIGO QR\n")
                p.qr(qr_data, size=10, ec=3)
                p.text("\n")
                p.set(align="center", bold=False)
                p.text("-" * WIDTH + "\n")
                p.set(align="center", bold=True)
                p.text("INSTRUCCIONES\n")
                p.set(align="left", bold=False)
                p.text("1. Conserve este ticket\n")
                p.text("2. Escanea el código QR\n")
                p.text("3. Retire su vehículo\n")
                p.text("-" * WIDTH + "\n")
                p.set(align="center", bold=False)
                p.text("Gracias por usar\n")
                p.text("nuestro servicio\n")
                p.text("=" * WIDTH + "\n")
                p.text("\n\n\n")
                
                # Try to cut paper
                try:
                    p.cut()
                except Exception:
                    p.text("\n\n\n")
                
                self.logger.info("Entry ticket printed: cabin=%s, ticket_id=%s", cabin_id, ticket_id)
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing entry ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing entry ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
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
            
            # Check connection health and reconnect if needed
            if not self._check_connection():
                self.logger.warning("Printer connection unavailable, using simulation mode")
                self._print_simulation(content)
                return True
            
            try:
                # Set encoding to CP850 for Spanish character support
                try:
                    self._printer.charcode("CP850")
                except Exception:
                    pass  # Continue if encoding fails
                
                # Print exit ticket
                self._printer.text("\n")
                self._printer.set(align="center", bold=True, font="a")
                self._printer.text("PARKING EXIT TICKET\n")
                self._printer.set(align="left", bold=False, font="a")
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
                
                self.logger.info("Exit ticket printed: vehicle=%s, cost=%s", vehicle_plate, cost)
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing exit ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing exit ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
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
            
            # Check connection health and reconnect if needed
            if not self._check_connection():
                self.logger.warning("Printer connection unavailable, using simulation mode")
                self._print_simulation(test_content)
                return True
            
            try:
                # Set encoding to CP850 for Spanish character support
                try:
                    self._printer.charcode("CP850")
                except Exception:
                    pass  # Continue if encoding fails
                
                # Print test ticket
                self._printer.text("\n")
                self._printer.set(align="center", bold=True, font="a")
                self._printer.text("PRINTER TEST TICKET\n")
                self._printer.set(align="left", bold=False, font="a")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("This is a test print from\n")
                self._printer.text("the Kiosko parking system.\n")
                self._printer.text(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                self._printer.text("=" * 32 + "\n")
                self._printer.text("\n\n")
                
                # Try to cut paper
                try:
                    self._printer.cut()
                except Exception as cut_error:
                    self.logger.warning("Paper cut failed: %s", cut_error)
                    # Send line feeds instead
                    self._printer.text("\n\n\n")
                
                self.logger.info("Test ticket printed successfully")
                return True
            except EscposError as e:
                self.logger.error("Printer error while printing test ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
                return False
            except Exception as e:
                self.logger.error("Unexpected error while printing test ticket: %s", e, exc_info=True)
                # Attempt to reconnect on error
                self._reconnect()
                return False

