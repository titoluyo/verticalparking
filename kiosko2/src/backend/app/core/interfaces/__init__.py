"""Abstract interfaces for dependency injection."""

from .repositories import ITicketRepository, ICabinRepository
from .services import IPresenceService, IMotorControlService, IPrinterService

__all__ = [
    "ITicketRepository",
    "ICabinRepository",
    "IPresenceService",
    "IMotorControlService",
    "IPrinterService",
]
