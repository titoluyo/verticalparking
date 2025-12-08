"""Cabin API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...core.services import CabinService
from ...core.models import Cabin, CabinStatus, CabinSensorState
from ...dependencies import get_cabin_service


router = APIRouter()


class CabinResponse(BaseModel):
    """Response for a single cabin."""
    id: str
    id_mqtt: Optional[str]
    estado: CabinStatus
    minimum_distance: Optional[int]
    is_active: bool
    sensor_state: CabinSensorState
    sensor_message: str
    is_at_floor: bool
    calibrating: bool


class CabinListResponse(BaseModel):
    """Response for cabin list."""
    cabins: List[CabinResponse]
    active_cabin: Optional[str]


class SetActiveCabinRequest(BaseModel):
    """Request to set active cabin."""
    cabin_id: str


class SetFloorLevelRequest(BaseModel):
    """Request to set floor level."""
    floor_level_mm: int


class CalibrationResponse(BaseModel):
    """Response for calibration operations."""
    success: bool
    message: str
    cabin_id: str


class MotorResponse(BaseModel):
    """Response for motor operations."""
    success: bool
    message: str


@router.get("/", response_model=CabinListResponse)
async def list_cabins(
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Get all cabins with their current status.
    
    Returns database state combined with real-time sensor data.
    """
    cabins = cabin_service.get_all_cabins()
    active_cabin = cabin_service.get_active_cabin()
    
    cabin_responses = [
        CabinResponse(
            id=c.id,
            id_mqtt=c.id_mqtt,
            estado=c.estado,
            minimum_distance=c.minimum_distance,
            is_active=c.is_active,
            sensor_state=c.sensor_state,
            sensor_message=c.sensor_message,
            is_at_floor=c.is_at_floor,
            calibrating=c.calibrating,
        )
        for c in cabins
    ]
    
    return CabinListResponse(
        cabins=cabin_responses,
        active_cabin=active_cabin,
    )


@router.get("/{cabin_id}", response_model=CabinResponse)
async def get_cabin(
    cabin_id: str,
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Get a specific cabin by ID.
    
    Accepts both CABINA-01 and cabina-01 formats.
    """
    cabin = cabin_service.get_cabin(cabin_id)
    
    if not cabin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cabin {cabin_id} not found",
        )
    
    return CabinResponse(
        id=cabin.id,
        id_mqtt=cabin.id_mqtt,
        estado=cabin.estado,
        minimum_distance=cabin.minimum_distance,
        is_active=cabin.is_active,
        sensor_state=cabin.sensor_state,
        sensor_message=cabin.sensor_message,
        is_at_floor=cabin.is_at_floor,
        calibrating=cabin.calibrating,
    )


@router.post("/active", response_model=dict)
async def set_active_cabin(
    request: SetActiveCabinRequest,
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Set the active cabin for vehicle entrance monitoring."""
    success = cabin_service.set_active_cabin(request.cabin_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cabin ID: {request.cabin_id}",
        )
    
    return {
        "success": True,
        "active_cabin": request.cabin_id,
        "message": "Active cabin updated",
    }


@router.get("/active/current")
async def get_active_cabin(
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Get the current active cabin."""
    active_cabin = cabin_service.get_active_cabin()
    return {"active_cabin": active_cabin}


@router.post("/{cabin_id}/floor-level")
async def set_floor_level(
    cabin_id: str,
    request: SetFloorLevelRequest,
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Set the floor level (minimum distance) for a cabin."""
    if request.floor_level_mm <= 0 or request.floor_level_mm > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="floor_level_mm must be between 1 and 5000",
        )
    
    success = cabin_service.set_floor_level(cabin_id, request.floor_level_mm)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cabin {cabin_id} not found",
        )
    
    return {
        "success": True,
        "cabin_id": cabin_id,
        "floor_level_mm": request.floor_level_mm,
    }


@router.post("/{cabin_id}/calibrate/start", response_model=CalibrationResponse)
async def start_calibration(
    cabin_id: str,
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Start calibration for a cabin."""
    success = cabin_service.start_calibration(cabin_id)
    
    if success:
        # Also start motor
        cabin_service.start_motor(cabin_id)
    
    return CalibrationResponse(
        success=success,
        message="Calibration started" if success else "Failed to start calibration",
        cabin_id=cabin_id,
    )


@router.post("/{cabin_id}/calibrate/stop", response_model=CalibrationResponse)
async def stop_calibration(
    cabin_id: str,
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Stop calibration for a cabin."""
    success = cabin_service.stop_calibration(cabin_id)
    cabin_service.stop_motor(cabin_id)  # Always stop motor
    
    return CalibrationResponse(
        success=success,
        message="Calibration stopped" if success else "Failed to stop calibration",
        cabin_id=cabin_id,
    )


@router.post("/motor/start", response_model=MotorResponse)
async def start_motor(
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Start the motor (global motor control)."""
    success = cabin_service.start_motor(None)
    
    return MotorResponse(
        success=success,
        message="Motor started" if success else "Failed to start motor",
    )


@router.post("/motor/stop", response_model=MotorResponse)
async def stop_motor(
    cabin_service: CabinService = Depends(get_cabin_service),
):
    """Stop the motor (global motor control)."""
    success = cabin_service.stop_motor(None)
    
    return MotorResponse(
        success=success,
        message="Motor stopped" if success else "Failed to stop motor",
    )
