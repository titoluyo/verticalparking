"""Dependency injection setup for FastAPI."""

import logging
from typing import Optional, Generator

from fastapi import Depends, HTTPException, Header, status

from .config import Settings, get_settings
from .core.interfaces import (
    ITicketRepository,
    ICabinRepository,
    IPresenceService,
    IMotorControlService,
    IPrinterService,
)
from .core.repositories import SQLiteTicketRepository, SQLiteCabinRepository
from .core.services import TicketService, CabinService


# Logging
def get_logger() -> logging.Logger:
    """Get application logger."""
    return logging.getLogger("kiosko2")


# Repositories
# Note: Do NOT use @lru_cache() with Depends() parameters.
# BaseSettings objects are unhashable, causing TypeError at runtime.
# FastAPI already caches dependencies per request, so caching is not needed here.
def get_ticket_repository(
    settings: Settings = Depends(get_settings),
) -> ITicketRepository:
    """Get ticket repository instance."""
    return SQLiteTicketRepository(settings.database_path)


def get_cabin_repository(
    settings: Settings = Depends(get_settings),
) -> ICabinRepository:
    """Get cabin repository instance."""
    return SQLiteCabinRepository(settings.database_path)


# External Services (initialized at startup)
_presence_service: Optional[IPresenceService] = None
_motor_service: Optional[IMotorControlService] = None
_printer_service: Optional[IPrinterService] = None


def set_presence_service(service: Optional[IPresenceService]) -> None:
    """Set the presence service instance (called at startup)."""
    global _presence_service
    _presence_service = service


def set_motor_service(service: Optional[IMotorControlService]) -> None:
    """Set the motor control service instance (called at startup)."""
    global _motor_service
    _motor_service = service


def set_printer_service(service: Optional[IPrinterService]) -> None:
    """Set the printer service instance (called at startup)."""
    global _printer_service
    _printer_service = service


def get_presence_service() -> Optional[IPresenceService]:
    """Get presence service instance."""
    return _presence_service


def get_motor_service() -> Optional[IMotorControlService]:
    """Get motor control service instance."""
    return _motor_service


def get_printer_service() -> Optional[IPrinterService]:
    """Get printer service instance."""
    return _printer_service


# Business Services
def get_ticket_service(
    ticket_repo: ITicketRepository = Depends(get_ticket_repository),
    cabin_repo: ICabinRepository = Depends(get_cabin_repository),
    logger: logging.Logger = Depends(get_logger),
) -> TicketService:
    """Get ticket service instance."""
    return TicketService(
        ticket_repository=ticket_repo,
        cabin_repository=cabin_repo,
        printer_service=_printer_service,
        logger=logger,
    )


def get_cabin_service(
    cabin_repo: ICabinRepository = Depends(get_cabin_repository),
    ticket_repo: ITicketRepository = Depends(get_ticket_repository),
    logger: logging.Logger = Depends(get_logger),
) -> CabinService:
    """Get cabin service instance."""
    return CabinService(
        cabin_repository=cabin_repo,
        ticket_repository=ticket_repo,
        presence_service=_presence_service,
        motor_service=_motor_service,
        logger=logger,
    )


# Security
def verify_api_key(
    x_test_api_key: Optional[str] = Header(None, alias="X-Test-API-Key"),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify API key for protected test endpoints.
    
    Raises:
        HTTPException: If API key is invalid or missing when required
    """
    if not settings.enable_test_endpoints:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are disabled",
        )
    
    if settings.api_key:
        if not x_test_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "X-Test-API-Key"},
            )
        if x_test_api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
    
    return True
