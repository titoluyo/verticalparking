"""Ticket domain model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TicketStatus(str, Enum):
    """Ticket status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TicketCreate(BaseModel):
    """DTO for creating a new ticket."""
    cabina_id: str = Field(..., description="Cabin ID where vehicle is stored")
    vehicle_plate: Optional[str] = Field(None, description="Vehicle license plate (optional)")


class Ticket(BaseModel):
    """Parking ticket domain model."""
    id: int = Field(..., description="Unique ticket ID")
    token: str = Field(..., description="Unique token for QR code")
    cabina_id: str = Field(..., description="Cabin ID where vehicle is stored")
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    exit_timestamp: Optional[datetime] = Field(None, description="Exit timestamp")
    vehicle_plate: Optional[str] = Field(None, description="Vehicle license plate")
    status: TicketStatus = Field(default=TicketStatus.ACTIVE, description="Ticket status")
    
    class Config:
        from_attributes = True
