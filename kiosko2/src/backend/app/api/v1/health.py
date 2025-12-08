"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...config import Settings, get_settings
from ...dependencies import get_presence_service, get_motor_service, get_printer_service


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    environment: str
    services: dict


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint."""
    presence = get_presence_service()
    motor = get_motor_service()
    printer = get_printer_service()
    
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        environment=settings.environment,
        services={
            "presence": "available" if presence else "unavailable",
            "motor_control": "available" if motor else "unavailable",
            "printer": "available" if printer else "unavailable",
        },
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness probe."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Kubernetes-style liveness probe."""
    return {"status": "alive"}
