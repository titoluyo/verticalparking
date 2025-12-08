"""Unit tests for TicketService."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from app.core.services.ticket_service import TicketService
from app.core.models import Ticket, TicketStatus, CabinStatus
from app.core.repositories.ticket_repository import InMemoryTicketRepository
from app.core.repositories.cabin_repository import InMemoryCabinRepository


class TestTicketService:
    """Test suite for TicketService."""
    
    @pytest.fixture
    def ticket_repo(self):
        """Create an in-memory ticket repository."""
        return InMemoryTicketRepository()
    
    @pytest.fixture
    def cabin_repo(self):
        """Create an in-memory cabin repository."""
        return InMemoryCabinRepository()
    
    @pytest.fixture
    def mock_printer(self):
        """Create a mock printer service."""
        printer = Mock()
        printer.print_entry_ticket.return_value = True
        return printer
    
    @pytest.fixture
    def ticket_service(self, ticket_repo, cabin_repo, mock_printer):
        """Create a TicketService with mocked dependencies."""
        return TicketService(
            ticket_repository=ticket_repo,
            cabin_repository=cabin_repo,
            printer_service=mock_printer,
        )
    
    def test_create_ticket_success(self, ticket_service, cabin_repo):
        """Test successful ticket creation."""
        cabin_id = "CABINA-01"
        
        ticket = ticket_service.create_ticket(
            cabina_id=cabin_id,
            vehicle_plate="ABC123",
            print_ticket=False,
        )
        
        assert ticket is not None
        assert ticket.cabina_id == cabin_id
        assert ticket.vehicle_plate == "ABC123"
        assert ticket.status == TicketStatus.ACTIVE
        assert ticket.token is not None
        
        # Cabin should be marked as busy
        cabin = cabin_repo.get(cabin_id)
        assert cabin.estado == CabinStatus.BUSY
    
    def test_create_ticket_with_print(self, ticket_service, mock_printer):
        """Test ticket creation with printing."""
        ticket = ticket_service.create_ticket(
            cabina_id="CABINA-02",
            vehicle_plate="",
            print_ticket=True,
        )
        
        assert ticket is not None
        mock_printer.print_entry_ticket.assert_called_once()
    
    def test_get_ticket_by_token(self, ticket_service):
        """Test retrieving ticket by token."""
        created = ticket_service.create_ticket(
            cabina_id="CABINA-03",
            print_ticket=False,
        )
        
        retrieved = ticket_service.get_ticket_by_token(created.token)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.token == created.token
    
    def test_get_ticket_with_parking_prefix(self, ticket_service):
        """Test retrieving ticket with PARKING: prefix."""
        created = ticket_service.create_ticket(
            cabina_id="CABINA-04",
            print_ticket=False,
        )
        
        # Should work with PARKING: prefix
        retrieved = ticket_service.get_ticket_by_token(f"PARKING:{created.token}")
        
        assert retrieved is not None
        assert retrieved.token == created.token
    
    def test_get_ticket_not_found(self, ticket_service):
        """Test retrieving non-existent ticket."""
        ticket = ticket_service.get_ticket_by_token("non-existent-token")
        assert ticket is None
    
    def test_validate_ticket_valid(self, ticket_service):
        """Test validating a valid ticket."""
        created = ticket_service.create_ticket(
            cabina_id="CABINA-05",
            print_ticket=False,
        )
        
        is_valid, message, ticket = ticket_service.validate_ticket(created.token)
        
        assert is_valid is True
        assert ticket is not None
        assert "valid" in message.lower()
    
    def test_validate_ticket_not_found(self, ticket_service):
        """Test validating a non-existent ticket."""
        is_valid, message, ticket = ticket_service.validate_ticket("invalid-token")
        
        assert is_valid is False
        assert ticket is None
        assert "not found" in message.lower()
    
    def test_complete_ticket(self, ticket_service, cabin_repo):
        """Test completing a ticket."""
        cabin_id = "CABINA-06"
        created = ticket_service.create_ticket(
            cabina_id=cabin_id,
            print_ticket=False,
        )
        
        # Cabin should be busy
        cabin = cabin_repo.get(cabin_id)
        assert cabin.estado == CabinStatus.BUSY
        
        # Complete the ticket
        success = ticket_service.complete_ticket(created.token)
        
        assert success is True
        
        # Cabin should be free again
        cabin = cabin_repo.get(cabin_id)
        assert cabin.estado == CabinStatus.FREE
    
    def test_complete_ticket_not_found(self, ticket_service):
        """Test completing a non-existent ticket."""
        success = ticket_service.complete_ticket("non-existent-token")
        assert success is False
    
    def test_cleanup_all_tickets(self, ticket_service, cabin_repo):
        """Test cleaning up all tickets."""
        # Create multiple tickets
        ticket_service.create_ticket(cabina_id="CABINA-01", print_ticket=False)
        ticket_service.create_ticket(cabina_id="CABINA-02", print_ticket=False)
        ticket_service.create_ticket(cabina_id="CABINA-03", print_ticket=False)
        
        # Cleanup
        count = ticket_service.cleanup_all_tickets()
        
        assert count == 3
        
        # All cabins should be free
        for i in range(1, 7):
            cabin = cabin_repo.get(f"CABINA-{i:02d}")
            assert cabin.estado == CabinStatus.FREE
