"""End-to-end tests for remote testing.

These tests are designed to run against a deployed instance.
They require API key authentication.
"""

import pytest
import os

# Skip these tests unless KIOSKO_REMOTE_URL is set
REMOTE_URL = os.getenv("KIOSKO_REMOTE_URL")
API_KEY = os.getenv("KIOSKO_TEST_API_KEY")


@pytest.mark.skipif(not REMOTE_URL, reason="KIOSKO_REMOTE_URL not set")
class TestRemoteE2E:
    """E2E tests against remote deployment."""
    
    @pytest.fixture
    def client(self):
        """Create an HTTP client for remote testing."""
        import httpx
        return httpx.Client(
            base_url=REMOTE_URL,
            headers={"X-Test-API-Key": API_KEY} if API_KEY else {},
            timeout=30.0,
        )
    
    def test_ping(self, client):
        """Test ping endpoint."""
        response = client.get("/api/v1/test/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pong"
    
    def test_store_and_retrieve_vehicle(self, client):
        """Test complete store and retrieve flow."""
        # 1. Cleanup first
        cleanup_response = client.post("/api/v1/test/cleanup")
        assert cleanup_response.status_code == 200
        
        # 2. Store a vehicle
        store_response = client.post(
            "/api/v1/test/store-vehicle",
            json={"cabin_id": "CABINA-01", "vehicle_plate": "TEST-123"},
        )
        assert store_response.status_code == 200
        store_data = store_response.json()
        assert store_data["success"] is True
        token = store_data["ticket_token"]
        
        # 3. Verify cabin is occupied
        cabin_response = client.get("/api/v1/cabins/CABINA-01")
        assert cabin_response.status_code == 200
        cabin_data = cabin_response.json()
        assert cabin_data["estado"] == "busy"
        
        # 4. Retrieve the vehicle
        retrieve_response = client.post(
            "/api/v1/test/retrieve-vehicle",
            json={"token": token},
        )
        assert retrieve_response.status_code == 200
        retrieve_data = retrieve_response.json()
        assert retrieve_data["success"] is True
        
        # 5. Verify cabin is free
        cabin_response = client.get("/api/v1/cabins/CABINA-01")
        assert cabin_response.status_code == 200
        cabin_data = cabin_response.json()
        assert cabin_data["estado"] == "free"
