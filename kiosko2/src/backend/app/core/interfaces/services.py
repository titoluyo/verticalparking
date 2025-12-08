"""Service interfaces for external dependencies."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, List


class IPresenceService(ABC):
    """Abstract interface for presence monitoring service."""
    
    @abstractmethod
    def start(self) -> None:
        """Start the presence monitoring service."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the presence monitoring service."""
        pass
    
    @abstractmethod
    def get_active_cabin(self) -> Optional[str]:
        """Get the current active cabin ID."""
        pass
    
    @abstractmethod
    def set_active_cabin(self, cabin_id: str) -> bool:
        """Set the active cabin for vehicle entrance monitoring.
        
        Args:
            cabin_id: The cabin ID to set as active
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def snapshot(self, cabin_id: Optional[str] = None) -> Dict[str, Any]:
        """Get snapshot of presence state.
        
        Args:
            cabin_id: Optional cabin ID to get state for
            
        Returns:
            Presence state dictionary
        """
        pass
    
    @abstractmethod
    def register_floor_reached_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for floor/reached events.
        
        Args:
            callback: Function called with (cabin_id, event_data) when floor is reached
        """
        pass
    
    @abstractmethod
    def register_calibration_complete_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for calibration/complete events.
        
        Args:
            callback: Function called with (cabin_id, event_data) when calibration completes
        """
        pass


class IMotorControlService(ABC):
    """Abstract interface for motor control service."""
    
    @abstractmethod
    def start_motor(self, cabin_id: Optional[str] = None) -> bool:
        """Start the motor.
        
        Args:
            cabin_id: Optional cabin ID (for logging)
            
        Returns:
            True if command sent successfully
        """
        pass
    
    @abstractmethod
    def stop_motor(self, cabin_id: Optional[str] = None) -> bool:
        """Stop the motor.
        
        Args:
            cabin_id: Optional cabin ID (for logging)
            
        Returns:
            True if command sent successfully
        """
        pass
    
    @abstractmethod
    def send_calibration_command(self, cabin_id: str, command: str) -> bool:
        """Send calibration command to a cabin.
        
        Args:
            cabin_id: Cabin ID
            command: Command type ("start" or "stop")
            
        Returns:
            True if command sent successfully
        """
        pass
    
    @abstractmethod
    def is_calibrating(self, cabin_id: str) -> bool:
        """Check if a cabin is currently calibrating.
        
        Args:
            cabin_id: Cabin ID to check
            
        Returns:
            True if cabin is calibrating
        """
        pass


class IPrinterService(ABC):
    """Abstract interface for printer service."""
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get printer status information.
        
        Returns:
            Status dictionary with available, status, status_detail, enabled keys
        """
        pass
    
    @abstractmethod
    def print_entry_ticket(
        self,
        vehicle_plate: str,
        cabin_id: str,
        timestamp: Optional[str] = None,
        ticket_id: Optional[str] = None,
        token: Optional[str] = None
    ) -> bool:
        """Print entry ticket.
        
        Args:
            vehicle_plate: Vehicle license plate
            cabin_id: Cabin identifier
            timestamp: Entry timestamp
            ticket_id: Ticket ID to display
            token: Full token for QR code
            
        Returns:
            True if print succeeded
        """
        pass
    
    @abstractmethod
    def print_exit_ticket(
        self,
        vehicle_plate: str,
        entry_time: str,
        exit_time: str,
        duration: str,
        cost: str
    ) -> bool:
        """Print exit ticket.
        
        Args:
            vehicle_plate: Vehicle license plate
            entry_time: Entry timestamp
            exit_time: Exit timestamp
            duration: Parking duration
            cost: Parking cost
            
        Returns:
            True if print succeeded
        """
        pass
    
    @abstractmethod
    def print_test(self) -> bool:
        """Print a test ticket.
        
        Returns:
            True if print succeeded
        """
        pass
