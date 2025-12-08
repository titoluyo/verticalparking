"""Unit tests for CabinService."""

import pytest
from unittest.mock import Mock

from app.core.services.cabin_service import CabinService
from app.core.models import CabinStatus, CabinSensorState
from app.core.repositories.ticket_repository import InMemoryTicketRepository
from app.core.repositories.cabin_repository import InMemoryCabinRepository


class TestCabinService:
    """Test suite for CabinService."""
    
    @pytest.fixture
    def ticket_repo(self):
        """Create an in-memory ticket repository."""
        return InMemoryTicketRepository()
    
    @pytest.fixture
    def cabin_repo(self):
        """Create an in-memory cabin repository."""
        return InMemoryCabinRepository()
    
    @pytest.fixture
    def mock_presence(self):
        """Create a mock presence service."""
        presence = Mock()
        presence.get_active_cabin.return_value = "cabina-01"
        presence.set_active_cabin.return_value = True
        presence.snapshot.return_value = {
            "state": "free",
            "message": "Espacio libre",
        }
        return presence
    
    @pytest.fixture
    def mock_motor(self):
        """Create a mock motor control service."""
        motor = Mock()
        motor.start_motor.return_value = True
        motor.stop_motor.return_value = True
        motor.send_calibration_command.return_value = True
        motor.is_calibrating.return_value = False
        return motor
    
    @pytest.fixture
    def cabin_service(self, cabin_repo, ticket_repo, mock_presence, mock_motor):
        """Create a CabinService with mocked dependencies."""
        return CabinService(
            cabin_repository=cabin_repo,
            ticket_repository=ticket_repo,
            presence_service=mock_presence,
            motor_service=mock_motor,
        )
    
    def test_get_cabin(self, cabin_service):
        """Test getting a specific cabin."""
        cabin = cabin_service.get_cabin("CABINA-01")
        
        assert cabin is not None
        assert cabin.id == "CABINA-01"
        assert cabin.id_mqtt == "cabina-01"
    
    def test_get_cabin_mqtt_format(self, cabin_service):
        """Test getting a cabin using MQTT format ID."""
        cabin = cabin_service.get_cabin("cabina-02")
        
        assert cabin is not None
        assert cabin.id == "CABINA-02"
    
    def test_get_cabin_not_found(self, cabin_service):
        """Test getting a non-existent cabin."""
        cabin = cabin_service.get_cabin("CABINA-99")
        assert cabin is None
    
    def test_get_all_cabins(self, cabin_service):
        """Test getting all cabins."""
        cabins = cabin_service.get_all_cabins()
        
        assert len(cabins) == 6
        assert all(c.id.startswith("CABINA-") for c in cabins)
    
    def test_find_next_free_cabin_circular(self, cabin_service, ticket_repo):
        """Test circular cabin search."""
        # All cabins should be free initially
        next_cabin = cabin_service.find_next_free_cabin_circular("CABINA-01")
        assert next_cabin == "CABINA-02"
        
        # Mark cabins 2 and 3 as having active tickets
        ticket_repo.create("token-1", "CABINA-02")
        ticket_repo.create("token-2", "CABINA-03")
        
        # Should skip to 04
        next_cabin = cabin_service.find_next_free_cabin_circular("CABINA-01")
        assert next_cabin == "CABINA-04"
    
    def test_find_next_free_cabin_wrap_around(self, cabin_service, ticket_repo):
        """Test circular search wrapping around."""
        # Mark cabins 05 and 06 as having tickets
        ticket_repo.create("token-1", "CABINA-05")
        ticket_repo.create("token-2", "CABINA-06")
        
        # Starting from 04, should wrap to 01
        next_cabin = cabin_service.find_next_free_cabin_circular("CABINA-04")
        assert next_cabin == "CABINA-01"
    
    def test_find_next_free_cabin_all_busy(self, cabin_service, ticket_repo):
        """Test when all cabins have tickets."""
        # Mark all cabins as having tickets
        for i in range(1, 7):
            ticket_repo.create(f"token-{i}", f"CABINA-{i:02d}")
        
        next_cabin = cabin_service.find_next_free_cabin_circular("CABINA-01")
        assert next_cabin is None
    
    def test_get_next_cabin_circular(self, cabin_service):
        """Test getting next cabin in circular order."""
        assert cabin_service.get_next_cabin_circular("CABINA-01") == "CABINA-02"
        assert cabin_service.get_next_cabin_circular("CABINA-05") == "CABINA-06"
        assert cabin_service.get_next_cabin_circular("CABINA-06") == "CABINA-01"  # Wrap
    
    def test_set_active_cabin(self, cabin_service, mock_presence):
        """Test setting active cabin."""
        success = cabin_service.set_active_cabin("cabina-03")
        
        assert success is True
        mock_presence.set_active_cabin.assert_called_once_with("cabina-03")
    
    def test_start_motor(self, cabin_service, mock_motor):
        """Test starting the motor."""
        success = cabin_service.start_motor("cabina-01")
        
        assert success is True
        mock_motor.start_motor.assert_called_once()
    
    def test_stop_motor(self, cabin_service, mock_motor):
        """Test stopping the motor."""
        success = cabin_service.stop_motor("cabina-01")
        
        assert success is True
        mock_motor.stop_motor.assert_called_once()
    
    def test_start_calibration(self, cabin_service, mock_motor):
        """Test starting calibration."""
        success = cabin_service.start_calibration("CABINA-01")
        
        assert success is True
        mock_motor.send_calibration_command.assert_called_once_with("cabina-01", "start")
    
    def test_set_floor_level(self, cabin_service, cabin_repo):
        """Test setting floor level."""
        success = cabin_service.set_floor_level("CABINA-01", 450)
        
        assert success is True
        
        cabin = cabin_repo.get("CABINA-01")
        assert cabin.minimum_distance == 450
    
    def test_reset_all_cabins(self, cabin_service, cabin_repo):
        """Test resetting all cabins."""
        # Mark some cabins as busy
        cabin_repo.update_status("CABINA-01", CabinStatus.BUSY)
        cabin_repo.update_status("CABINA-02", CabinStatus.BUSY)
        
        count = cabin_service.reset_all_cabins()
        
        assert count == 6
        
        # All should be free now
        for cabin in cabin_repo.get_all():
            assert cabin.estado == CabinStatus.FREE
