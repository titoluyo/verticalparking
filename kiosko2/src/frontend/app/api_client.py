"""Backend API client for the Flask frontend."""

import logging
from typing import Optional, Dict, Any, List
import requests
from requests.exceptions import RequestException


class BackendClient:
    """Client for communicating with the FastAPI backend."""
    
    def __init__(self, base_url: str, timeout: int = 10):
        """Initialize the backend client.
        
        Args:
            base_url: Base URL of the backend API (e.g., "http://localhost:8000")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the backend.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/api/v1/cabins")
            json: JSON body for POST requests
            params: Query parameters
            
        Returns:
            Response JSON or error dict
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=json,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            self.logger.error(f"Backend request failed: {method} {url} - {e}")
            return {"error": str(e), "success": False}
    
    # Health endpoints
    def health_check(self) -> Dict[str, Any]:
        """Check backend health."""
        return self._request("GET", "/api/v1/health")
    
    # Cabin endpoints
    def get_cabins(self) -> List[Dict[str, Any]]:
        """Get all cabins with their status."""
        result = self._request("GET", "/api/v1/cabins/")
        if "error" in result:
            return []
        return result.get("cabins", [])
    
    def get_cabin(self, cabin_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific cabin."""
        result = self._request("GET", f"/api/v1/cabins/{cabin_id}")
        if "error" in result:
            return None
        return result
    
    def get_active_cabin(self) -> Optional[str]:
        """Get the current active cabin."""
        result = self._request("GET", "/api/v1/cabins/active/current")
        return result.get("active_cabin")
    
    def set_active_cabin(self, cabin_id: str) -> bool:
        """Set the active cabin."""
        result = self._request("POST", "/api/v1/cabins/active", json={"cabin_id": cabin_id})
        return result.get("success", False)
    
    def start_motor(self) -> bool:
        """Start the motor."""
        result = self._request("POST", "/api/v1/cabins/motor/start")
        return result.get("success", False)
    
    def stop_motor(self) -> bool:
        """Stop the motor."""
        result = self._request("POST", "/api/v1/cabins/motor/stop")
        return result.get("success", False)
    
    def start_calibration(self, cabin_id: str) -> bool:
        """Start calibration for a cabin."""
        result = self._request("POST", f"/api/v1/cabins/{cabin_id}/calibrate/start")
        return result.get("success", False)
    
    def stop_calibration(self, cabin_id: str) -> bool:
        """Stop calibration for a cabin."""
        result = self._request("POST", f"/api/v1/cabins/{cabin_id}/calibrate/stop")
        return result.get("success", False)
    
    def set_floor_level(self, cabin_id: str, floor_level_mm: int) -> bool:
        """Set floor level for a cabin."""
        result = self._request(
            "POST",
            f"/api/v1/cabins/{cabin_id}/floor-level",
            json={"floor_level_mm": floor_level_mm},
        )
        return result.get("success", False)
    
    # Ticket endpoints
    def create_ticket(
        self,
        cabin_id: str,
        vehicle_plate: str = "",
        print_ticket: bool = True,
    ) -> Dict[str, Any]:
        """Create a new ticket."""
        return self._request(
            "POST",
            "/api/v1/tickets/",
            json={
                "cabina_id": cabin_id,
                "vehicle_plate": vehicle_plate,
                "print_ticket": print_ticket,
            },
        )
    
    def get_ticket(self, token: str) -> Optional[Dict[str, Any]]:
        """Get ticket by token."""
        result = self._request("GET", f"/api/v1/tickets/{token}")
        if "error" in result or not result.get("valid"):
            return None
        return result.get("ticket")
    
    def scan_ticket(self, token: str) -> Dict[str, Any]:
        """Scan a QR code and validate the ticket."""
        return self._request("POST", "/api/v1/tickets/scan", json={"token": token})
    
    def complete_ticket(self, token: str) -> bool:
        """Complete a ticket (vehicle retrieved)."""
        result = self._request("POST", f"/api/v1/tickets/{token}/complete")
        return result.get("success", False)
    
    # Presence endpoints
    def get_presence(self, cabin_id: Optional[str] = None) -> Dict[str, Any]:
        """Get presence status."""
        if cabin_id:
            return self._request("GET", f"/api/v1/presence/{cabin_id}")
        return self._request("GET", "/api/v1/presence/")
