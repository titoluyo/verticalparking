"""Ticket API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...core.services import TicketService
from ...core.models import Ticket
from ...dependencies import get_ticket_service


router = APIRouter()


class CreateTicketRequest(BaseModel):
    """Request body for creating a ticket."""
    cabina_id: str
    vehicle_plate: Optional[str] = None
    print_ticket: bool = True


class CreateTicketResponse(BaseModel):
    """Response for ticket creation."""
    success: bool
    ticket_id: Optional[int] = None
    token: Optional[str] = None
    cabina_id: Optional[str] = None
    message: str


class ValidateTicketResponse(BaseModel):
    """Response for ticket validation."""
    valid: bool
    message: str
    ticket: Optional[Ticket] = None


class ScanTicketRequest(BaseModel):
    """Request body for scanning a ticket."""
    token: str


class ScanTicketResponse(BaseModel):
    """Response for ticket scan."""
    success: bool
    message: str
    ticket: Optional[Ticket] = None
    cabina_id: Optional[str] = None


@router.post("/", response_model=CreateTicketResponse)
async def create_ticket(
    request: CreateTicketRequest,
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Create a new parking ticket.
    
    Creates a ticket for the specified cabin, marks the cabin as busy,
    and optionally prints the ticket.
    """
    ticket = ticket_service.create_ticket(
        cabina_id=request.cabina_id,
        vehicle_plate=request.vehicle_plate,
        print_ticket=request.print_ticket,
    )
    
    if not ticket:
        return CreateTicketResponse(
            success=False,
            message="Failed to create ticket",
        )
    
    return CreateTicketResponse(
        success=True,
        ticket_id=ticket.id,
        token=ticket.token,
        cabina_id=ticket.cabina_id,
        message=f"Ticket created for {ticket.cabina_id}",
    )


@router.get("/{token}", response_model=ValidateTicketResponse)
async def get_ticket(
    token: str,
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Get ticket by token.
    
    Validates and returns ticket information for the given token.
    """
    is_valid, message, ticket = ticket_service.validate_ticket(token)
    
    return ValidateTicketResponse(
        valid=is_valid,
        message=message,
        ticket=ticket,
    )


@router.post("/scan", response_model=ScanTicketResponse)
async def scan_ticket(
    request: ScanTicketRequest,
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Scan a QR code and validate the ticket.
    
    Accepts tokens in either "PARKING:uuid" or "uuid" format.
    """
    ticket = ticket_service.get_ticket_by_token(request.token)
    
    if not ticket:
        return ScanTicketResponse(
            success=False,
            message="Ticket not found",
        )
    
    if ticket.status != "active":
        return ScanTicketResponse(
            success=False,
            message=f"Ticket is {ticket.status}",
            ticket=ticket,
            cabina_id=ticket.cabina_id,
        )
    
    return ScanTicketResponse(
        success=True,
        message=f"Valid ticket for {ticket.cabina_id}",
        ticket=ticket,
        cabina_id=ticket.cabina_id,
    )


@router.post("/{token}/complete")
async def complete_ticket(
    token: str,
    ticket_service: TicketService = Depends(get_ticket_service),
):
    """Mark a ticket as completed (vehicle retrieved).
    
    Updates ticket status and frees the associated cabin.
    """
    success = ticket_service.complete_ticket(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or already completed",
        )
    
    return {"success": True, "message": "Ticket completed"}
