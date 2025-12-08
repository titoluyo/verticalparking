"""Cabin domain model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CabinStatus(str, Enum):
    """Cabin status enumeration."""
    FREE = "free"
    BUSY = "busy"


class CabinSensorState(str, Enum):
    """Cabin sensor-derived state."""
    FREE = "free"
    TRANSITIONING = "transitioning"
    OCCUPIED = "occupied"
    ENTERED = "entered"
    UNKNOWN = "unknown"


class SensorData(BaseModel):
    """Sensor data for a cabin."""
    present: bool = False
    ts: Optional[float] = None


class DistanceData(BaseModel):
    """Distance sensor data for a cabin."""
    mm: Optional[int] = None
    min_mm: Optional[int] = None  # Floor level (minimum distance)
    ts: Optional[float] = None


class CabinSensors(BaseModel):
    """Aggregated sensor data for a cabin."""
    entry: SensorData = Field(default_factory=SensorData)
    full: SensorData = Field(default_factory=SensorData)
    distance: DistanceData = Field(default_factory=DistanceData)


class Cabin(BaseModel):
    """Parking cabin domain model."""
    id: str = Field(..., description="Cabin ID (e.g., 'CABINA-01')")
    estado: CabinStatus = Field(default=CabinStatus.FREE, description="Cabin database status")
    minimum_distance: Optional[int] = Field(None, description="Floor level distance in mm")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Runtime sensor state (not persisted)
    id_mqtt: Optional[str] = Field(None, description="MQTT-format cabin ID (e.g., 'cabina-01')")
    is_active: bool = Field(default=False, description="Whether this is the active cabin")
    sensors: Optional[CabinSensors] = Field(None, description="Current sensor readings")
    sensor_state: CabinSensorState = Field(default=CabinSensorState.UNKNOWN, description="Sensor-derived state")
    sensor_message: str = Field(default="", description="Human-readable sensor state message")
    is_at_floor: bool = Field(default=False, description="Whether cabin is at floor level")
    calibrating: bool = Field(default=False, description="Whether cabin is calibrating")
    
    class Config:
        from_attributes = True
    
    @staticmethod
    def db_id_to_mqtt(db_id: str) -> str:
        """Convert DB format (CABINA-01) to MQTT format (cabina-01)."""
        if db_id.startswith("CABINA-"):
            return db_id.replace("CABINA-", "cabina-").lower()
        return db_id.lower()
    
    @staticmethod
    def mqtt_id_to_db(mqtt_id: str) -> str:
        """Convert MQTT format (cabina-01) to DB format (CABINA-01)."""
        if mqtt_id.startswith("cabina-"):
            return mqtt_id.replace("cabina-", "CABINA-").upper()
        return mqtt_id.upper()
