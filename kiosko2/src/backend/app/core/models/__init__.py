"""Domain models for the parking system."""

from .ticket import Ticket, TicketStatus, TicketCreate
from .cabin import Cabin, CabinStatus, CabinSensorState

__all__ = [
    "Ticket",
    "TicketStatus",
    "TicketCreate",
    "Cabin",
    "CabinStatus",
    "CabinSensorState",
]
