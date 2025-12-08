"""Presence API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...dependencies import get_presence_service


router = APIRouter()


class PresenceSnapshot(BaseModel):
    """Presence state snapshot."""
    entry: dict
    full: dict
    distance: dict
    state: str
    message: str
    connected: bool


@router.get("/", response_model=PresenceSnapshot)
async def get_presence():
    """Get presence status for the active cabin."""
    presence = get_presence_service()
    
    if not presence:
        raise HTTPException(
            status_code=503,
            detail="Presence service unavailable",
        )
    
    snapshot = presence.snapshot()
    if "error" in snapshot:
        raise HTTPException(
            status_code=404,
            detail=snapshot["error"],
        )
    
    return PresenceSnapshot(**snapshot)


@router.get("/{cabin_id}", response_model=PresenceSnapshot)
async def get_cabin_presence(cabin_id: str):
    """Get presence status for a specific cabin."""
    presence = get_presence_service()
    
    if not presence:
        raise HTTPException(
            status_code=503,
            detail="Presence service unavailable",
        )
    
    snapshot = presence.snapshot(cabin_id=cabin_id)
    if "error" in snapshot:
        raise HTTPException(
            status_code=404,
            detail=snapshot["error"],
        )
    
    return PresenceSnapshot(**snapshot)
