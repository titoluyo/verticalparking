"""MQTT-based presence monitoring service."""

import json
import logging
import threading
import time
from typing import Optional, Dict, Any, Callable, List

import paho.mqtt.client as mqtt

from ...core.interfaces.services import IPresenceService


class PresenceService(IPresenceService):
    """MQTT-based presence monitoring service.
    
    Subscribes to presence topics for multiple cabins and maintains
    real-time sensor state in memory.
    """
    
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cabins: Optional[List[str]] = None,
        topic_base: str = "parking",
        site: str = "garage-01",
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.cabins = cabins or [f"cabina-{i:02d}" for i in range(1, 7)]
        self.topic_base = topic_base
        self.site = site
        self.client_id = client_id or f"kiosko2-presence-{int(time.time())}"
        self.logger = logger or logging.getLogger(__name__)
        
        self._lock = threading.Lock()
        self._state: Dict[str, Dict[str, Any]] = {}
        self._active_cabin: Optional[str] = sorted(self.cabins)[0] if self.cabins else None
        
        # Callbacks
        self._floor_reached_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._calibration_complete_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._callbacks_lock = threading.Lock()
        
        # Initialize state for each cabin
        for cabin in self.cabins:
            self._state[cabin] = {
                "entry": {"present": False, "ts": None},
                "full": {"present": False, "ts": None},
                "previous": (False, False),
                "distance": {"from_mm": None, "to_mm": None, "ts": None},
            }
        
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """Start the presence monitoring service."""
        if self._thread and self._thread.is_alive():
            self.logger.warning("PresenceService already running")
            return
        
        self.logger.info(f"Starting PresenceService: broker={self.broker}:{self.port}, cabins={self.cabins}")
        self._thread = threading.Thread(target=self._run, name="presence-mqtt", daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the presence monitoring service."""
        self._stop_event.set()
    
    def get_active_cabin(self) -> Optional[str]:
        """Get the current active cabin ID."""
        with self._lock:
            return self._active_cabin
    
    def set_active_cabin(self, cabin_id: str) -> bool:
        """Set the active cabin."""
        with self._lock:
            if cabin_id not in self.cabins:
                self.logger.warning(f"Invalid cabin ID: {cabin_id}")
                return False
            
            old = self._active_cabin
            self._active_cabin = cabin_id
            
            # Reset previous state for new active cabin
            if cabin_id in self._state:
                entry = bool(self._state[cabin_id]["entry"]["present"])
                full = bool(self._state[cabin_id]["full"]["present"])
                self._state[cabin_id]["previous"] = (entry, full)
            
            self.logger.info(f"Active cabin changed: {old} -> {cabin_id}")
            return True
    
    def snapshot(self, cabin_id: Optional[str] = None) -> Dict[str, Any]:
        """Get snapshot of presence state."""
        with self._lock:
            target = cabin_id or self._active_cabin
            if not target or target not in self._state:
                return {"error": f"Cabin {target} not found"}
            
            cabin_state = self._state[target]
            entry_present = bool(cabin_state["entry"]["present"])
            full_present = bool(cabin_state["full"]["present"])
            prev_entry, prev_full = cabin_state.get("previous", (False, False))
            
            state_info = self._determine_state(entry_present, full_present, prev_entry, prev_full)
            
            return {
                "entry": {"present": entry_present, "ts": cabin_state["entry"]["ts"]},
                "full": {"present": full_present, "ts": cabin_state["full"]["ts"]},
                "distance": cabin_state.get("distance", {}),
                "state": state_info["state"],
                "message": state_info["message"],
                "connected": self._connected,
            }
    
    def register_floor_reached_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for floor/reached events."""
        with self._callbacks_lock:
            self._floor_reached_callbacks.append(callback)
    
    def register_calibration_complete_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for calibration/complete events."""
        with self._callbacks_lock:
            self._calibration_complete_callbacks.append(callback)
    
    def _run(self) -> None:
        """Main MQTT loop."""
        client = mqtt.Client(client_id=self.client_id, clean_session=True)
        if self.username:
            client.username_pw_set(self.username, self.password)
        
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        
        while not self._stop_event.is_set():
            try:
                self.logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
                client.connect(self.broker, self.port, keepalive=30)
                client.loop_forever()
            except Exception as e:
                self.logger.error(f"MQTT error: {e}")
                self._connected = False
                if self._stop_event.wait(timeout=5):
                    break
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self._connected = True
            self.logger.info("Connected to MQTT broker")
            
            # Subscribe to all cabin topics
            for cabin in self.cabins:
                topics = [
                    f"{self.topic_base}/{self.site}/{cabin}/presence/entry",
                    f"{self.topic_base}/{self.site}/{cabin}/presence/full",
                    f"{self.topic_base}/{self.site}/{cabin}/distance/event",
                    f"{self.topic_base}/{self.site}/{cabin}/floor/reached",
                    f"{self.topic_base}/{self.site}/{cabin}/calibration/complete",
                ]
                for topic in topics:
                    client.subscribe(topic, qos=1)
                    self.logger.debug(f"Subscribed to {topic}")
        else:
            self.logger.error(f"MQTT connect failed: rc={rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self._connected = False
        self.logger.warning(f"Disconnected from MQTT broker: rc={rc}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            device = payload.get("device", "")
            ts = payload.get("ts") or time.time()
            
            # Extract cabin ID
            cabin_id = None
            if device.startswith("cabina-"):
                cabin_id = device
            else:
                parts = msg.topic.split("/")
                if len(parts) >= 3 and parts[2].startswith("cabina-"):
                    cabin_id = parts[2]
            
            if not cabin_id or cabin_id not in self.cabins:
                return
            
            # Handle different message types
            if "floor/reached" in msg.topic:
                self._handle_floor_reached(cabin_id, payload, ts)
            elif "calibration/complete" in msg.topic:
                self._handle_calibration_complete(cabin_id, payload, ts)
            elif "distance" in msg.topic:
                self._handle_distance(cabin_id, payload, ts)
            elif "presence" in msg.topic:
                sensor = payload.get("sensor", "")
                present = bool(payload.get("present"))
                
                if sensor == "ir1" or "entry" in msg.topic:
                    self._update_state(cabin_id, "entry", present, ts)
                elif sensor == "ir2" or "full" in msg.topic:
                    self._update_state(cabin_id, "full", present, ts)
                    
        except Exception as e:
            self.logger.warning(f"Error processing MQTT message: {e}")
    
    def _update_state(self, cabin_id: str, key: str, present: bool, ts: float) -> None:
        """Update sensor state for a cabin."""
        with self._lock:
            if cabin_id not in self._state:
                return
            
            old_entry = bool(self._state[cabin_id]["entry"]["present"])
            old_full = bool(self._state[cabin_id]["full"]["present"])
            
            self._state[cabin_id][key] = {"present": present, "ts": ts}
            self._state[cabin_id]["previous"] = (old_entry, old_full)
    
    def _handle_distance(self, cabin_id: str, payload: Dict, ts: float) -> None:
        """Handle distance sensor message."""
        with self._lock:
            if cabin_id not in self._state:
                return
            
            self._state[cabin_id]["distance"] = {
                "from_mm": payload.get("from_mm"),
                "to_mm": payload.get("to_mm"),
                "ts": ts,
            }
    
    def _handle_floor_reached(self, cabin_id: str, payload: Dict, ts: float) -> None:
        """Handle floor reached event."""
        self.logger.info(f"Floor reached: {cabin_id}")
        
        with self._callbacks_lock:
            for callback in self._floor_reached_callbacks:
                try:
                    callback(cabin_id, {
                        "distance_mm": payload.get("distance_mm"),
                        "floor_level_mm": payload.get("floor_level_mm"),
                        "ts": ts,
                    })
                except Exception as e:
                    self.logger.error(f"Error in floor callback: {e}")
    
    def _handle_calibration_complete(self, cabin_id: str, payload: Dict, ts: float) -> None:
        """Handle calibration complete event."""
        self.logger.info(f"Calibration complete: {cabin_id}")
        
        with self._callbacks_lock:
            for callback in self._calibration_complete_callbacks:
                try:
                    callback(cabin_id, {
                        "floor_level_mm": payload.get("floor_level_mm"),
                        "calibration_rounds": payload.get("calibration_rounds"),
                        "ts": ts,
                    })
                except Exception as e:
                    self.logger.error(f"Error in calibration callback: {e}")
    
    def _determine_state(self, entry: bool, full: bool, prev_entry: bool, prev_full: bool) -> Dict[str, str]:
        """Determine state from sensor values."""
        if not entry and not full:
            return {"state": "free", "message": "Espacio libre"}
        elif entry and not full:
            if not prev_entry and not prev_full:
                return {"state": "transitioning", "message": "Vehículo ingresando..."}
            else:
                return {"state": "transitioning", "message": "Vehículo saliendo..."}
        elif entry and full:
            return {"state": "entered", "message": "Vehículo ingresado"}
        else:
            return {"state": "free", "message": "Espacio libre"}
