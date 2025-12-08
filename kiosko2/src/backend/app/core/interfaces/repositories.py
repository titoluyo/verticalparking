"""Repository interfaces for data access abstraction."""

from abc import ABC, abstractmethod
from typing import Optional, List

from ..models import Ticket, TicketCreate, Cabin, CabinStatus


class ITicketRepository(ABC):
    """Abstract interface for ticket data operations."""
    
    @abstractmethod
    def create(self, token: str, cabina_id: str, vehicle_plate: Optional[str] = None) -> int:
        """Create a new ticket.
        
        Args:
            token: Unique token for QR code
            cabina_id: Cabin ID where vehicle is stored
            vehicle_plate: Optional vehicle license plate
            
        Returns:
            Ticket ID
        """
        pass
    
    @abstractmethod
    def get_by_token(self, token: str) -> Optional[Ticket]:
        """Get ticket by token.
        
        Args:
            token: Ticket token
            
        Returns:
            Ticket or None if not found
        """
        pass
    
    @abstractmethod
    def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """Get ticket by ID.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            Ticket or None if not found
        """
        pass
    
    @abstractmethod
    def has_active_ticket(self, cabina_id: str) -> bool:
        """Check if a cabin has an active ticket.
        
        Args:
            cabina_id: Cabin ID to check
            
        Returns:
            True if cabin has an active ticket
        """
        pass
    
    @abstractmethod
    def complete_ticket(self, token: str) -> bool:
        """Mark a ticket as completed.
        
        Args:
            token: Ticket token
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete_all(self) -> int:
        """Delete all tickets.
        
        Returns:
            Number of tickets deleted
        """
        pass


class ICabinRepository(ABC):
    """Abstract interface for cabin data operations."""
    
    @abstractmethod
    def get(self, cabina_id: str) -> Optional[Cabin]:
        """Get cabin by ID.
        
        Args:
            cabina_id: Cabin ID
            
        Returns:
            Cabin or None if not found
        """
        pass
    
    @abstractmethod
    def get_all(self) -> List[Cabin]:
        """Get all cabins ordered by ID.
        
        Returns:
            List of cabins
        """
        pass
    
    @abstractmethod
    def update_status(self, cabina_id: str, estado: CabinStatus) -> bool:
        """Update cabin status.
        
        Args:
            cabina_id: Cabin ID
            estado: New status
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def update_minimum_distance(self, cabina_id: str, minimum_distance: int) -> bool:
        """Update minimum distance (floor level) for a cabin.
        
        Args:
            cabina_id: Cabin ID
            minimum_distance: Minimum distance in mm
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def find_free_cabin(self) -> Optional[str]:
        """Find the first available free cabin.
        
        Returns:
            Cabin ID or None if no free cabins
        """
        pass
    
    @abstractmethod
    def reset_all(self) -> int:
        """Reset all cabins to free status.
        
        Returns:
            Number of cabins reset
        """
        pass
