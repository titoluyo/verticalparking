"""Ticket business logic service."""

import uuid
import logging
from datetime import datetime
from typing import Optional

from ..interfaces.repositories import ITicketRepository, ICabinRepository
from ..interfaces.services import IPrinterService
from ..models import Ticket, CabinStatus


class TicketService:
    """Business logic for ticket operations.
    
    Follows Single Responsibility Principle: handles only ticket-related business logic.
    Uses Dependency Inversion: depends on abstractions (interfaces), not concrete implementations.
    """
    
    def __init__(
        self,
        ticket_repository: ITicketRepository,
        cabin_repository: ICabinRepository,
        printer_service: Optional[IPrinterService] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize TicketService with dependencies.
        
        Args:
            ticket_repository: Repository for ticket data operations
            cabin_repository: Repository for cabin data operations
            printer_service: Optional printer service for ticket printing
            logger: Optional logger instance
        """
        self._ticket_repo = ticket_repository
        self._cabin_repo = cabin_repository
        self._printer = printer_service
        self._logger = logger or logging.getLogger(__name__)
    
    def create_ticket(
        self,
        cabina_id: str,
        vehicle_plate: Optional[str] = None,
        print_ticket: bool = True,
    ) -> Optional[Ticket]:
        """Create a new parking ticket.
        
        Args:
            cabina_id: Cabin ID where vehicle is stored
            vehicle_plate: Optional vehicle license plate
            print_ticket: Whether to print the ticket
            
        Returns:
            Created ticket or None if creation failed
        """
        # Generate unique token for QR code
        token = str(uuid.uuid4())
        
        # Create ticket in database
        try:
            ticket_id = self._ticket_repo.create(
                token=token,
                cabina_id=cabina_id,
                vehicle_plate=vehicle_plate,
            )
            
            if not ticket_id:
                self._logger.error("Failed to create ticket in database")
                return None
            
            # Mark cabin as busy
            self._cabin_repo.update_status(cabina_id, CabinStatus.BUSY)
            
            # Get created ticket
            ticket = self._ticket_repo.get_by_id(ticket_id)
            if not ticket:
                self._logger.error(f"Failed to retrieve created ticket {ticket_id}")
                return None
            
            self._logger.info(f"Created ticket {ticket_id} for cabin {cabina_id}")
            
            # Print ticket if requested
            if print_ticket and self._printer:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._printer.print_entry_ticket(
                    vehicle_plate=vehicle_plate or "",
                    cabin_id=cabina_id,
                    timestamp=timestamp,
                    ticket_id=token[:8].upper(),
                    token=token,
                )
            
            return ticket
            
        except Exception as e:
            self._logger.error(f"Error creating ticket: {e}", exc_info=True)
            return None
    
    def get_ticket_by_token(self, token: str) -> Optional[Ticket]:
        """Get ticket by token.
        
        Args:
            token: Ticket token (may include PARKING: prefix)
            
        Returns:
            Ticket or None if not found
        """
        # Handle "PARKING:uuid" format
        if token.startswith("PARKING:"):
            token = token[8:]
        
        return self._ticket_repo.get_by_token(token)
    
    def validate_ticket(self, token: str) -> tuple[bool, str, Optional[Ticket]]:
        """Validate a ticket for vehicle retrieval.
        
        Args:
            token: Ticket token
            
        Returns:
            Tuple of (is_valid, message, ticket)
        """
        ticket = self.get_ticket_by_token(token)
        
        if not ticket:
            return False, "Ticket not found", None
        
        if ticket.status != "active":
            return False, f"Ticket is {ticket.status}", ticket
        
        return True, "Ticket is valid", ticket
    
    def complete_ticket(self, token: str) -> bool:
        """Complete a ticket (vehicle retrieved).
        
        Args:
            token: Ticket token
            
        Returns:
            True if successful
        """
        ticket = self.get_ticket_by_token(token)
        if not ticket:
            return False
        
        # Mark ticket as completed
        success = self._ticket_repo.complete_ticket(token)
        
        if success:
            # Mark cabin as free
            self._cabin_repo.update_status(ticket.cabina_id, CabinStatus.FREE)
            self._logger.info(f"Completed ticket {token[:8]} for cabin {ticket.cabina_id}")
        
        return success
    
    def cleanup_all_tickets(self) -> int:
        """Delete all tickets and reset cabins.
        
        Returns:
            Number of tickets deleted
        """
        count = self._ticket_repo.delete_all()
        self._cabin_repo.reset_all()
        self._logger.info(f"Cleaned up {count} tickets and reset all cabins")
        return count
