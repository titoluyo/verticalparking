"""Protected test endpoints for remote E2E testing.

These endpoints are protected by API key and can be disabled in production.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...dependencies import verify_api_key, get_ticket_service, get_cabin_service
from ...core.services import TicketService, CabinService


router = APIRouter()


class CleanupResponse(BaseModel):
    """Response for cleanup operation."""
    success: bool
    tickets_deleted: int
    cabins_reset: int


class TestStoreVehicleRequest(BaseModel):
    """Request for test store vehicle."""
    cabin_id: str
    vehicle_plate: str = ""


class TestStoreVehicleResponse(BaseModel):
    """Response for test store vehicle."""
    success: bool
    ticket_token: str = ""
    cabin_id: str = ""
    message: str


class TestRetrieveVehicleRequest(BaseModel):
    """Request for test retrieve vehicle."""
    token: str


class TestRetrieveVehicleResponse(BaseModel):
    """Response for test retrieve vehicle."""
    success: bool
    cabin_id: str = ""
    message: str


@router.post("/cleanup", response_model=CleanupResponse)
async def test_cleanup(
    _: bool = Depends(verify_api_key),
    ticket_service: TicketService = Depends(get_ticket_service),
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Clean up all tickets and reset all cabins.
    
    This endpoint is protected by API key and can be used to reset
    the system state during E2E testing.
    """
    tickets_deleted = ticket_service.cleanup_all_tickets()
    cabins_reset = cabin_service.reset_all_cabins()
    
    return CleanupResponse(
        success=True,
        tickets_deleted=tickets_deleted,
        cabins_reset=cabins_reset,
    )


@router.post("/store-vehicle", response_model=TestStoreVehicleResponse)
async def test_store_vehicle(
    request: TestStoreVehicleRequest,
    _: bool = Depends(verify_api_key),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Test storing a vehicle in a specific cabin.
    
    Creates a ticket and marks the cabin as busy.
    """
    ticket = ticket_service.create_ticket(
        cabina_id=request.cabin_id,
        vehicle_plate=request.vehicle_plate,
        print_ticket=False,  # Don't print during tests
    )
    
    if not ticket:
        return TestStoreVehicleResponse(
            success=False,
            message="Failed to store vehicle",
        )
    
    return TestStoreVehicleResponse(
        success=True,
        ticket_token=ticket.token,
        cabin_id=ticket.cabina_id,
        message=f"Vehicle stored in {ticket.cabina_id}",
    )


@router.post("/retrieve-vehicle", response_model=TestRetrieveVehicleResponse)
async def test_retrieve_vehicle(
    request: TestRetrieveVehicleRequest,
    _: bool = Depends(verify_api_key),
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Test retrieving a vehicle using its ticket token.
    
    Validates the ticket and marks it as completed.
    """
    is_valid, message, ticket = ticket_service.validate_ticket(request.token)
    
    if not is_valid or not ticket:
        return TestRetrieveVehicleResponse(
            success=False,
            message=message,
        )
    
    success = ticket_service.complete_ticket(request.token)
    
    return TestRetrieveVehicleResponse(
        success=success,
        cabin_id=ticket.cabina_id if success else "",
        message="Vehicle retrieved" if success else "Failed to retrieve vehicle",
    )


@router.get("/ping")
async def test_ping(_: bool = Depends(verify_api_key)):
    """Simple ping endpoint to verify API key authentication works."""
    return {"status": "pong", "message": "API key verified"}
