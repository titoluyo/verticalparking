"""
Motor control service for vertical parking system.
Handles starting/stopping the motor and monitoring cabin position to reach floor level.
"""
import json
import logging
import threading
import time
from typing import Optional, Callable
import paho.mqtt.client as mqtt


class MotorControlService:
    """Service to control motor and monitor cabin movement to floor level."""
    
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        site: str = "garage-01",
        topic_base: str = "parking",
        logger: Optional[logging.Logger] = None
    ):
        """Initialize motor control service.
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
            username: MQTT username (optional)
            password: MQTT password (optional)
            site: Site ID (e.g., "garage-01")
            topic_base: MQTT topic base (default: "parking")
            logger: Optional logger instance
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.site = site
        self.topic_base = topic_base
        self.logger = logger or logging.getLogger(__name__)
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._target_cabin: Optional[str] = None
        self._minimum_distance: Optional[int] = None
        self._stop_callback: Optional[Callable[[str], None]] = None
        self._distance_cache: dict = {}
        self._lock = threading.Lock()
        
        # Calibration state per cabin
        self._calibration_state: Dict[str, bool] = {}  # {cabin_id: is_calibrating}
        
        # MQTT client for commands (separate from monitoring)
        self._command_client: Optional[mqtt.Client] = None
    
    def send_motor_command(self, command: str) -> bool:
        """Send motor control command via MQTT.
        
        The motor control system uses a single global topic for all cabins:
        - Topic: parking/{site}/motor
        - Messages: "ON" to start motor, "OFF" to stop motor
        
        Args:
            command: Command value ("ON" or "OFF")
        
        Returns:
            True if command sent successfully
        """
        try:
            # Motor control uses a single global topic, not per-cabin
            topic = f"{self.topic_base}/{self.site}/motor"
            
            # Ensure command is uppercase
            command = command.upper()
            if command not in ["ON", "OFF"]:
                self.logger.error(f"Invalid motor command: {command}. Must be 'ON' or 'OFF'")
                return False
            
            # Create temporary MQTT client for command
            client = mqtt.Client(client_id=f"motor-control-{int(time.time())}")
            if self.username and self.password:
                client.username_pw_set(self.username, self.password)
            
            client.connect(self.broker, self.port, 60)
            client.publish(topic, command, qos=1, retain=False)
            client.disconnect()
            
            self.logger.info(f"Sent motor command '{command}' via topic: {topic}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending motor command: {e}", exc_info=True)
            return False
    
    def start_motor(self, cabin_id: str = None) -> bool:
        """Start the motor to move cabin.
        
        Args:
            cabin_id: Optional cabin ID (for logging, motor control is global)
        
        Returns:
            True if command sent successfully
        """
        return self.send_motor_command("ON")
    
    def stop_motor(self, cabin_id: str = None) -> bool:
        """Stop the motor.
        
        Args:
            cabin_id: Optional cabin ID (for logging, motor control is global)
        
        Returns:
            True if command sent successfully
        """
        return self.send_motor_command("OFF")
    
    def send_calibration_command(self, cabin_id: str, command: str) -> bool:
        """Send calibration command to a cabin via MQTT.
        
        Args:
            cabin_id: Cabin ID (e.g., "cabina-01")
            command: Command type ("start" or "stop")
        
        Returns:
            True if command sent successfully
        """
        try:
            # Build command topic: parking/{site}/{cabin_id}/cmd
            topic = f"{self.topic_base}/{self.site}/{cabin_id}/cmd"
            
            # Build JSON payload
            if command.lower() == "start":
                payload = json.dumps({"start_calibration": True})
                with self._lock:
                    self._calibration_state[cabin_id] = True
            elif command.lower() == "stop":
                payload = json.dumps({"stop_calibration": True})
                with self._lock:
                    self._calibration_state[cabin_id] = False
            else:
                self.logger.error(f"Invalid calibration command: {command}. Must be 'start' or 'stop'")
                return False
            
            # Create temporary MQTT client for command
            client = mqtt.Client(client_id=f"motor-calibration-{int(time.time())}")
            if self.username and self.password:
                client.username_pw_set(self.username, self.password)
            
            client.connect(self.broker, self.port, 60)
            client.publish(topic, payload, qos=1, retain=False)
            client.disconnect()
            
            self.logger.info(f"Sent calibration {command} command to {cabin_id} via topic: {topic}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending calibration command: {e}", exc_info=True)
            return False
    
    def is_calibrating(self, cabin_id: str) -> bool:
        """Check if a cabin is currently calibrating.
        
        Args:
            cabin_id: Cabin ID to check
        
        Returns:
            True if cabin is calibrating
        """
        with self._lock:
            return self._calibration_state.get(cabin_id, False)
    
    def move_to_floor(self, cabin_id: str = None) -> bool:
        """Send command to move cabin to floor level (starts motor).
        
        Args:
            cabin_id: Optional cabin ID (for logging)
        
        Returns:
            True if command sent successfully
        """
        return self.start_motor(cabin_id)
    
    def start_monitoring(
        self,
        target_cabin: str,
        minimum_distance: int,
        presence_service,
        stop_callback: Optional[Callable[[str], None]] = None,
        tolerance: int = 10
    ) -> bool:
        """Start monitoring target cabin distance and stop motor when floor is reached.
        
        Args:
            target_cabin: Cabin ID to monitor (e.g., "cabina-02")
            minimum_distance: Floor level distance in mm
            presence_service: PresenceService instance to get distance data
            stop_callback: Optional callback when floor is reached (called with cabin_id)
            tolerance: Tolerance in mm for considering at floor (default: 10mm)
        
        Returns:
            True if monitoring started successfully
        """
        with self._lock:
            if self._monitoring:
                self.logger.warning(f"Already monitoring {self._target_cabin}, stopping first")
                self.stop_monitoring()
            
            self._target_cabin = target_cabin
            self._minimum_distance = minimum_distance
            self._stop_callback = stop_callback
            self._monitoring = True
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_distance,
            args=(target_cabin, minimum_distance, presence_service, tolerance),
            name=f"motor-monitor-{target_cabin}",
            daemon=True
        )
        self._monitor_thread.start()
        
        self.logger.info(f"Started monitoring {target_cabin} for floor arrival (min_distance={minimum_distance}mm)")
        return True
    
    def stop_monitoring(self) -> None:
        """Stop monitoring distance."""
        with self._lock:
            if not self._monitoring:
                return
            
            self._monitoring = False
            self._target_cabin = None
            self._minimum_distance = None
            self._stop_callback = None
        
        self.logger.info("Stopped monitoring distance")
    
    def _is_at_floor(self, current_distance: Optional[int], minimum_distance: Optional[int], tolerance: int = 10) -> bool:
        """Check if cabin is at floor level.
        
        Args:
            current_distance: Current distance reading in mm
            minimum_distance: Minimum distance (floor level) in mm
            tolerance: Tolerance in mm
        
        Returns:
            True if at floor level
        """
        if current_distance is None or minimum_distance is None:
            return False
        
        return abs(current_distance - minimum_distance) <= tolerance
    
    def _monitor_distance(
        self,
        target_cabin: str,
        minimum_distance: int,
        presence_service,
        tolerance: int
    ) -> None:
        """Monitor distance in background thread.
        
        Args:
            target_cabin: Cabin ID to monitor
            minimum_distance: Floor level distance in mm
            presence_service: PresenceService instance
            tolerance: Tolerance in mm
        """
        check_interval = 0.5  # Check every 500ms
        consecutive_checks = 3  # Require 3 consecutive checks at floor before stopping
        
        at_floor_count = 0
        
        self.logger.info(f"Starting distance monitoring for {target_cabin} (target: {minimum_distance}mm ±{tolerance}mm)")
        
        while True:
            with self._lock:
                if not self._monitoring or self._target_cabin != target_cabin:
                    break
            
            try:
                # Get current distance from presence service
                snapshot = presence_service.snapshot(cabin_id=target_cabin)
                
                # Extract distance from snapshot
                current_distance = None
                if isinstance(snapshot, dict):
                    distance_data = snapshot.get("distance")
                    if distance_data and isinstance(distance_data, dict):
                        current_distance = distance_data.get("mm")
                    
                    # Also check min_mm from snapshot
                    if distance_data and isinstance(distance_data, dict):
                        snapshot_min = distance_data.get("min_mm")
                        if snapshot_min and minimum_distance != snapshot_min:
                            self.logger.info(f"Updating minimum distance from snapshot: {snapshot_min}mm")
                            minimum_distance = snapshot_min
                
                # Check if at floor
                if self._is_at_floor(current_distance, minimum_distance, tolerance):
                    at_floor_count += 1
                    self.logger.debug(
                        f"{target_cabin} at floor check {at_floor_count}/{consecutive_checks} "
                        f"(distance={current_distance}mm, target={minimum_distance}mm)"
                    )
                    
                    if at_floor_count >= consecutive_checks:
                        # Reached floor - stop motor and notify
                        self.logger.info(
                            f"{target_cabin} reached floor level! "
                            f"Distance: {current_distance}mm (target: {minimum_distance}mm ±{tolerance}mm)"
                        )
                        
                        # Stop motor
                        self.stop_motor(target_cabin)
                        
                        # Call callback if provided
                        if self._stop_callback:
                            try:
                                self._stop_callback(target_cabin)
                            except Exception as e:
                                self.logger.error(f"Error in stop callback: {e}", exc_info=True)
                        
                        # Stop monitoring
                        self.stop_monitoring()
                        return
                else:
                    # Reset counter if not at floor
                    if at_floor_count > 0:
                        self.logger.debug(f"{target_cabin} moved away from floor (distance={current_distance}mm)")
                        at_floor_count = 0
                
            except Exception as e:
                self.logger.error(f"Error monitoring distance for {target_cabin}: {e}", exc_info=True)
            
            time.sleep(check_interval)
        
        self.logger.info(f"Stopped monitoring {target_cabin}")
