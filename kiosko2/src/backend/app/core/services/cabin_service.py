"""Cabin business logic service."""

import logging
from typing import Optional, List

from ..interfaces.repositories import ITicketRepository, ICabinRepository
from ..interfaces.services import IPresenceService, IMotorControlService
from ..models import Cabin, CabinStatus, CabinSensorState


class CabinService:
    """Business logic for cabin operations.
    
    Follows Single Responsibility Principle: handles only cabin-related business logic.
    Uses Dependency Inversion: depends on abstractions (interfaces), not concrete implementations.
    """
    
    def __init__(
        self,
        cabin_repository: ICabinRepository,
        ticket_repository: ITicketRepository,
        presence_service: Optional[IPresenceService] = None,
        motor_service: Optional[IMotorControlService] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize CabinService with dependencies.
        
        Args:
            cabin_repository: Repository for cabin data operations
            ticket_repository: Repository for ticket data operations (for active ticket checks)
            presence_service: Optional presence monitoring service
            motor_service: Optional motor control service
            logger: Optional logger instance
        """
        self._cabin_repo = cabin_repository
        self._ticket_repo = ticket_repository
        self._presence = presence_service
        self._motor = motor_service
        self._logger = logger or logging.getLogger(__name__)
    
    def get_cabin(self, cabin_id: str) -> Optional[Cabin]:
        """Get cabin by ID with sensor data.
        
        Args:
            cabin_id: Cabin ID (accepts both CABINA-01 and cabina-01 formats)
            
        Returns:
            Cabin with sensor data or None if not found
        """
        # Normalize cabin ID to DB format
        db_id = self._normalize_to_db_id(cabin_id)
        
        cabin = self._cabin_repo.get(db_id)
        if cabin:
            self._enrich_cabin_with_sensor_data(cabin)
        return cabin
    
    def get_all_cabins(self) -> List[Cabin]:
        """Get all cabins with sensor data.
        
        Returns:
            List of cabins with sensor data
        """
        cabins = self._cabin_repo.get_all()
        for cabin in cabins:
            self._enrich_cabin_with_sensor_data(cabin)
        return cabins
    
    def find_next_free_cabin_circular(self, start_cabin_id: Optional[str] = None) -> Optional[str]:
        """Find the next free cabin in circular order (01→02→03→04→05→06→01).
        
        A cabin is considered free if it has no active ticket.
        
        Args:
            start_cabin_id: Cabin ID to start searching from. Search starts from the NEXT cabin.
                           If None, searches all cabins starting from CABINA-01.
            
        Returns:
            Cabin ID of next free cabin, or None if no free cabins
        """
        all_cabins = self._cabin_repo.get_all()
        if not all_cabins:
            return None
        
        cabin_list = [c.id for c in all_cabins]  # ["CABINA-01", "CABINA-02", ...]
        
        # If no start cabin provided, search all cabins starting from the first one
        if not start_cabin_id:
            for cabin_id in cabin_list:
                if not self._ticket_repo.has_active_ticket(cabin_id):
                    self._logger.info(f"Found free cabin: {cabin_id}")
                    return cabin_id
            self._logger.warning("No free cabins found")
            return None
        
        # Determine starting index
        db_id = self._normalize_to_db_id(start_cabin_id)
        try:
            start_idx = cabin_list.index(db_id)
        except ValueError:
            start_idx = 0
        
        # Search circularly starting from NEXT cabin after start_idx
        # First pass: from start_idx+1 to end
        for i in range(start_idx + 1, len(cabin_list)):
            cabin_id = cabin_list[i]
            if not self._ticket_repo.has_active_ticket(cabin_id):
                self._logger.info(f"Found free cabin: {cabin_id}")
                return cabin_id
        
        # Second pass: from beginning to start_idx (wrap around, inclusive of start_idx)
        for i in range(0, start_idx + 1):
            cabin_id = cabin_list[i]
            if not self._ticket_repo.has_active_ticket(cabin_id):
                self._logger.info(f"Found free cabin (wrapped): {cabin_id}")
                return cabin_id
        
        self._logger.warning("No free cabins found in circular search")
        return None
    
    def get_next_cabin_circular(self, current_cabin_id: str) -> str:
        """Get the next cabin in circular order.
        
        Args:
            current_cabin_id: Current cabin ID
            
        Returns:
            Next cabin ID in circular order
        """
        db_id = self._normalize_to_db_id(current_cabin_id)
        
        # Extract number
        if db_id.startswith("CABINA-"):
            num_str = db_id[7:]
        else:
            num_str = db_id
        
        try:
            cabin_num = int(num_str)
            # Circular: 1-6, wraps 6→1
            next_num = (cabin_num % 6) + 1
            return f"CABINA-{next_num:02d}"
        except (ValueError, TypeError):
            return "CABINA-01"
    
    def set_active_cabin(self, cabin_id: str) -> bool:
        """Set the active cabin for vehicle entrance.
        
        Args:
            cabin_id: Cabin ID to set as active
            
        Returns:
            True if successful
        """
        if not self._presence:
            self._logger.warning("Cannot set active cabin - presence service unavailable")
            return False
        
        mqtt_id = self._normalize_to_mqtt_id(cabin_id)
        return self._presence.set_active_cabin(mqtt_id)
    
    def get_active_cabin(self) -> Optional[str]:
        """Get the current active cabin ID.
        
        Returns:
            Active cabin ID in MQTT format, or None
        """
        if not self._presence:
            return None
        return self._presence.get_active_cabin()
    
    def start_motor(self, cabin_id: str) -> bool:
        """Start motor to move cabin.
        
        Args:
            cabin_id: Cabin ID
            
        Returns:
            True if successful
        """
        if not self._motor:
            self._logger.warning("Cannot start motor - motor service unavailable")
            return False
        
        return self._motor.start_motor(cabin_id)
    
    def stop_motor(self, cabin_id: str) -> bool:
        """Stop motor.
        
        Args:
            cabin_id: Cabin ID
            
        Returns:
            True if successful
        """
        if not self._motor:
            self._logger.warning("Cannot stop motor - motor service unavailable")
            return False
        
        return self._motor.stop_motor(cabin_id)
    
    def start_calibration(self, cabin_id: str) -> bool:
        """Start calibration for a cabin.
        
        Args:
            cabin_id: Cabin ID
            
        Returns:
            True if successful
        """
        if not self._motor:
            self._logger.warning("Cannot calibrate - motor service unavailable")
            return False
        
        mqtt_id = self._normalize_to_mqtt_id(cabin_id)
        return self._motor.send_calibration_command(mqtt_id, "start")
    
    def stop_calibration(self, cabin_id: str) -> bool:
        """Stop calibration for a cabin.
        
        Args:
            cabin_id: Cabin ID
            
        Returns:
            True if successful
        """
        if not self._motor:
            return False
        
        mqtt_id = self._normalize_to_mqtt_id(cabin_id)
        return self._motor.send_calibration_command(mqtt_id, "stop")
    
    def set_floor_level(self, cabin_id: str, floor_level_mm: int) -> bool:
        """Set the floor level for a cabin.
        
        Args:
            cabin_id: Cabin ID
            floor_level_mm: Floor level distance in mm
            
        Returns:
            True if successful
        """
        db_id = self._normalize_to_db_id(cabin_id)
        return self._cabin_repo.update_minimum_distance(db_id, floor_level_mm)
    
    def reset_all_cabins(self) -> int:
        """Reset all cabins to free status.
        
        Returns:
            Number of cabins reset
        """
        return self._cabin_repo.reset_all()
    
    def _normalize_to_db_id(self, cabin_id: str) -> str:
        """Normalize cabin ID to DB format (CABINA-01)."""
        if cabin_id.startswith("cabina-"):
            return cabin_id.replace("cabina-", "CABINA-").upper()
        elif cabin_id.startswith("CABINA-"):
            return cabin_id
        else:
            # Try to parse as number
            try:
                num = int(cabin_id)
                return f"CABINA-{num:02d}"
            except ValueError:
                return cabin_id
    
    def _normalize_to_mqtt_id(self, cabin_id: str) -> str:
        """Normalize cabin ID to MQTT format (cabina-01)."""
        if cabin_id.startswith("CABINA-"):
            return cabin_id.replace("CABINA-", "cabina-").lower()
        elif cabin_id.startswith("cabina-"):
            return cabin_id.lower()
        else:
            try:
                num = int(cabin_id)
                return f"cabina-{num:02d}"
            except ValueError:
                return cabin_id.lower()
    
    def _enrich_cabin_with_sensor_data(self, cabin: Cabin) -> None:
        """Enrich cabin with real-time sensor data."""
        if not self._presence:
            cabin.sensor_state = CabinSensorState.UNKNOWN
            cabin.sensor_message = "Sensor no disponible"
            return
        
        mqtt_id = cabin.id_mqtt or self._normalize_to_mqtt_id(cabin.id)
        
        # Check if this is the active cabin
        active_cabin = self._presence.get_active_cabin()
        cabin.is_active = (mqtt_id == active_cabin)
        
        # Check calibration status
        if self._motor:
            cabin.calibrating = self._motor.is_calibrating(mqtt_id)
        
        # Get sensor data from presence service
        try:
            snapshot = self._presence.snapshot(cabin_id=mqtt_id)
            if snapshot and not snapshot.get("error"):
                cabin.sensor_state = CabinSensorState(snapshot.get("state", "unknown"))
                cabin.sensor_message = snapshot.get("message", "")
                
                # Check floor level
                distance = snapshot.get("distance", {})
                if distance:
                    current_mm = distance.get("to_mm")
                    min_mm = distance.get("min_mm") or cabin.minimum_distance
                    if current_mm is not None and min_mm is not None:
                        cabin.is_at_floor = current_mm <= min_mm
        except Exception as e:
            self._logger.warning(f"Error getting sensor data for {cabin.id}: {e}")
        
        # Override with ticket-based status
        if self._ticket_repo.has_active_ticket(cabin.id):
            cabin.sensor_state = CabinSensorState.OCCUPIED
            cabin.sensor_message = "Vehículo guardado"
