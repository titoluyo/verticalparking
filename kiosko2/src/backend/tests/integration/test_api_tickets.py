"""Integration tests for ticket API endpoints."""

import pytest
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import init_database, get_settings


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    init_database(db_path)
    yield db_path
    
    # Cleanup
    try:
        db_path.unlink()
    except:
        pass


@pytest.fixture
def client(test_db, monkeypatch):
    """Create a test client with test database."""
    # Override database path
    monkeypatch.setenv("KIOSKO_DATABASE_PATH", str(test_db))
    monkeypatch.setenv("KIOSKO_MQTT_BROKER", "localhost")  # Won't connect in tests
    
    # Clear cached settings
    from app.config import get_settings
    get_settings.cache_clear()
    
    app = create_app()
    
    with TestClient(app) as client:
        yield client


class TestTicketAPI:
    """Integration tests for ticket endpoints."""
    
    def test_create_ticket(self, client):
        """Test creating a ticket via API."""
        response = client.post(
            "/api/v1/tickets/",
            json={
                "cabina_id": "CABINA-01",
                "vehicle_plate": "ABC123",
                "print_ticket": False,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cabina_id"] == "CABINA-01"
        assert "token" in data
    
    def test_get_ticket(self, client):
        """Test getting a ticket by token."""
        # Create a ticket first
        create_response = client.post(
            "/api/v1/tickets/",
            json={"cabina_id": "CABINA-02", "print_ticket": False},
        )
        token = create_response.json()["token"]
        
        # Get the ticket
        response = client.get(f"/api/v1/tickets/{token}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["ticket"]["cabina_id"] == "CABINA-02"
    
    def test_get_ticket_not_found(self, client):
        """Test getting a non-existent ticket."""
        response = client.get("/api/v1/tickets/non-existent-token")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
    
    def test_scan_ticket(self, client):
        """Test scanning a ticket."""
        # Create a ticket
        create_response = client.post(
            "/api/v1/tickets/",
            json={"cabina_id": "CABINA-03", "print_ticket": False},
        )
        token = create_response.json()["token"]
        
        # Scan the ticket
        response = client.post(
            "/api/v1/tickets/scan",
            json={"token": token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cabina_id"] == "CABINA-03"
    
    def test_scan_ticket_with_prefix(self, client):
        """Test scanning a ticket with PARKING: prefix."""
        # Create a ticket
        create_response = client.post(
            "/api/v1/tickets/",
            json={"cabina_id": "CABINA-04", "print_ticket": False},
        )
        token = create_response.json()["token"]
        
        # Scan with prefix
        response = client.post(
            "/api/v1/tickets/scan",
            json={"token": f"PARKING:{token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_complete_ticket(self, client):
        """Test completing a ticket."""
        # Create a ticket
        create_response = client.post(
            "/api/v1/tickets/",
            json={"cabina_id": "CABINA-05", "print_ticket": False},
        )
        token = create_response.json()["token"]
        
        # Complete the ticket
        response = client.post(f"/api/v1/tickets/{token}/complete")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify ticket is now completed
        get_response = client.get(f"/api/v1/tickets/{token}")
        assert get_response.json()["valid"] is False  # No longer active


class TestCabinAPI:
    """Integration tests for cabin endpoints."""
    
    def test_list_cabins(self, client):
        """Test listing all cabins."""
        response = client.get("/api/v1/cabins/")
        
        assert response.status_code == 200
        data = response.json()
        assert "cabins" in data
        assert len(data["cabins"]) == 6
    
    def test_get_cabin(self, client):
        """Test getting a specific cabin."""
        response = client.get("/api/v1/cabins/CABINA-01")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "CABINA-01"
        assert data["id_mqtt"] == "cabina-01"
    
    def test_get_cabin_mqtt_format(self, client):
        """Test getting a cabin by MQTT format ID."""
        response = client.get("/api/v1/cabins/cabina-02")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "CABINA-02"
    
    def test_get_cabin_not_found(self, client):
        """Test getting a non-existent cabin."""
        response = client.get("/api/v1/cabins/CABINA-99")
        
        assert response.status_code == 404
    
    def test_set_floor_level(self, client):
        """Test setting floor level."""
        response = client.post(
            "/api/v1/cabins/CABINA-01/floor-level",
            json={"floor_level_mm": 450},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["floor_level_mm"] == 450
    
    def test_set_floor_level_invalid(self, client):
        """Test setting invalid floor level."""
        response = client.post(
            "/api/v1/cabins/CABINA-01/floor-level",
            json={"floor_level_mm": 10000},  # Too high
        )
        
        assert response.status_code == 400


class TestHealthAPI:
    """Integration tests for health endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_readiness_check(self, client):
        """Test readiness probe."""
        response = client.get("/api/v1/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    def test_liveness_check(self, client):
        """Test liveness probe."""
        response = client.get("/api/v1/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
