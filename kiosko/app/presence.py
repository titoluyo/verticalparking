"""Background MQTT presence consumer used by the kiosk UI."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import paho.mqtt.client as mqtt


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or fallback


def _iso(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class PresenceService:
    """Subscribes to retained presence topics and stores the latest state in memory.
    
    Monitors two IR sensors per cabin:
    - Entry sensor (IR1): Detects when a vehicle starts entering the cabin
    - Full sensor (IR2): Detects when a vehicle is fully entered into the cabin
    
    Supports single-cabin mode (backward compatible) or multi-cabin mode.
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topic_entry: Optional[str] = None,
        topic_full: Optional[str] = None,
        cabins: Optional[list[str]] = None,
        topic_base: Optional[str] = None,
        site: Optional[str] = None,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_entry = topic_entry
        self.topic_full = topic_full
        self.cabins = cabins  # List of cabin IDs (e.g., ["cabina-01", "cabina-02", ...])
        self.topic_base = topic_base
        self.site = site
        self.client_id = client_id or f"kiosko-presence-{int(time.time())}"
        self.logger = logger or logging.getLogger(__name__)

        self._lock = threading.Lock()
        # Multi-cabin state: {cabin_id: {"entry": {...}, "full": {...}, "previous": (bool, bool)}}
        # Single-cabin mode: {"entry": {...}, "full": {...}}
        self._state: Dict[str, Any] = {}
        self._multi_cabin_mode = cabins is not None and len(cabins) > 0
        # Active cabin for vehicle entrance monitoring (only one active at a time)
        self._active_cabin: Optional[str] = None
        
        # Callbacks for floor and calibration events
        self._floor_reached_callbacks: list[Callable[[str, Dict[str, Any]], None]] = []
        self._calibration_complete_callbacks: list[Callable[[str, Dict[str, Any]], None]] = []
        self._callbacks_lock = threading.Lock()
        if self._multi_cabin_mode and cabins:
            # Default to first cabin
            self._active_cabin = cabins[0]
            self.logger.info("Active cabin initialized to: %s", self._active_cabin)
        
        if self._multi_cabin_mode:
            # Initialize state for each cabin
            for cabin in cabins:
                self._state[cabin] = {
                    "entry": {"present": False, "ts": None},
                    "full": {"present": False, "ts": None},
                    "previous": (False, False),
                    "distance": {"from_mm": None, "to_mm": None, "ts": None},
                }
        else:
            # Single-cabin mode (backward compatible)
            self._state = {
                "entry": {"present": False, "ts": None},
                "full": {"present": False, "ts": None},
                "distance": {"from_mm": None, "to_mm": None, "ts": None},
            }
            self._previous_combined_state: Optional[Tuple[bool, bool]] = None  # (entry, full)
        
        self._status = "initializing"
        self._status_detail: Optional[str] = None
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # SSE subscribers: list of queues for each connected client
        self._subscribers: list[queue.Queue] = []
        self._subscribers_lock = threading.Lock()
        self.logger.debug("PresenceService initialized client_id=%s multi_cabin=%s", 
                         self.client_id, self._multi_cabin_mode)

    # Factory -----------------------------------------------------------------
    @classmethod
    def from_env(cls, logger: Optional[logging.Logger] = None) -> "PresenceService":
        broker = _env("KIOSKO_MQTT_HOST", _env("MQTT_BROKER", "127.0.0.1"))
        port = int(_env("KIOSKO_MQTT_PORT", _env("MQTT_PORT", "1883")))
        username = _env("KIOSKO_MQTT_USER", _env("MQTT_USER"))
        password = _env("KIOSKO_MQTT_PASSWORD", _env("MQTT_PASSWORD"))

        topic_base = _env("KIOSKO_TOPIC_BASE", _env("TOPIC_BASE", "parking"))
        site = _env("KIOSKO_SITE_ID", _env("SITE_ID", "garage-01"))
        
        device = _env("KIOSKO_DEVICE_ID", _env("DEVICE_ID"))
        cabins_str = _env("KIOSKO_CABINS")  # e.g., "cabina-01-cabina-06" or "cabina-01,cabina-02,cabina-03"
        
        # Single-cabin mode: Use if DEVICE_ID is explicitly set and KIOSKO_CABINS is not set
        if device and not cabins_str:
            topic_entry = _env("KIOSKO_TOPIC_ENTRY") or f"{topic_base}/{site}/{device}/presence/entry"
            topic_full = _env("KIOSKO_TOPIC_FULL") or f"{topic_base}/{site}/{device}/presence/full"
            return cls(
                broker=broker,
                port=port,
                username=username,
                password=password,
                topic_entry=topic_entry,
                topic_full=topic_full,
                client_id=f"kiosko-{device}",
                logger=logger,
            )
        
        # Multi-cabin mode: Parse cabins or default to cabina-01 to cabina-06
        cabins = None
        if cabins_str:
            # Parse cabin range or list
            if "-" in cabins_str:
                # Try to parse as range format: "cabina-01-cabina-06" or "cabina-01-06"
                try:
                    # Check if it's "cabina-XX-cabina-YY" format
                    if cabins_str.startswith("cabina-") and cabins_str.count("cabina-") == 2:
                        # Format: "cabina-01-cabina-06"
                        parts = cabins_str.split("cabina-")
                        start_num = int(parts[1].split("-")[0])
                        end_num = int(parts[2])
                        cabins = [f"cabina-{i:02d}" for i in range(start_num, end_num + 1)]
                    elif cabins_str.startswith("cabina-"):
                        # Format: "cabina-01-06"
                        parts = cabins_str.split("-")
                        if len(parts) == 3:
                            start_num = int(parts[1])
                            end_num = int(parts[2])
                            cabins = [f"cabina-{i:02d}" for i in range(start_num, end_num + 1)]
                        else:
                            raise ValueError("Invalid range format")
                    else:
                        raise ValueError("Invalid range format")
                except (ValueError, IndexError):
                    if logger:
                        logger.warning("Invalid cabin range format: %s, defaulting to cabina-01-cabina-06", cabins_str)
                    cabins = None
            else:
                # Comma-separated list: "cabina-01,cabina-02,cabina-03"
                cabins = [c.strip() for c in cabins_str.split(",") if c.strip()]
        
        # Default to cabina-01 to cabina-06 if no cabins specified
        if not cabins:
            cabins = [f"cabina-{i:02d}" for i in range(1, 7)]  # cabina-01 to cabina-06
        
        # Multi-cabin mode
        return cls(
            broker=broker,
            port=port,
            username=username,
            password=password,
            cabins=cabins,
            topic_base=topic_base,
            site=site,
            client_id="kiosko-multi-cabin",
            logger=logger,
        )

    # Public API ---------------------------------------------------------------
    def start(self) -> None:
        self.logger.debug("PresenceService start called")
        if self._thread and self._thread.is_alive():
            self.logger.warning("PresenceService already started")
            return
        if self._multi_cabin_mode:
            self.logger.info(
                "Starting presence watcher (multi-cabin) broker=%s | cabins=%s | site=%s | active_cabin=%s",
                self.broker,
                ",".join(self.cabins),
                self.site,
                self._active_cabin,
            )
        else:
            self.logger.info(
                "Starting presence watcher broker=%s | topics entry=%s | full=%s",
                self.broker,
                self.topic_entry,
                self.topic_full,
            )
        self._thread = threading.Thread(target=self._run, name="presence-mqtt", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
    
    def subscribe(self) -> queue.Queue:
        """Subscribe to presence state updates. Returns a queue that will receive snapshot dicts."""
        # Use a small queue size to prevent memory issues if client disconnects
        client_queue: queue.Queue = queue.Queue(maxsize=10)
        with self._subscribers_lock:
            self._subscribers.append(client_queue)
        self.logger.debug("New SSE subscriber registered, total subscribers: %d", len(self._subscribers))
        return client_queue
    
    def unsubscribe(self, client_queue: queue.Queue) -> None:
        """Unsubscribe from presence state updates."""
        with self._subscribers_lock:
            try:
                self._subscribers.remove(client_queue)
                self.logger.debug("SSE subscriber unregistered, remaining subscribers: %d", len(self._subscribers))
            except ValueError:
                pass  # Already removed

    def get_active_cabin(self) -> Optional[str]:
        """Get the current active cabin ID."""
        with self._lock:
            return self._active_cabin
    
    def register_floor_reached_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for floor/reached events.
        
        Args:
            callback: Function that will be called with (cabin_id, event_data) when floor is reached
        """
        with self._callbacks_lock:
            self._floor_reached_callbacks.append(callback)
    
    def register_calibration_complete_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for calibration/complete events.
        
        Args:
            callback: Function that will be called with (cabin_id, event_data) when calibration completes
        """
        with self._callbacks_lock:
            self._calibration_complete_callbacks.append(callback)
    
    def set_active_cabin(self, cabin_id: str) -> bool:
        """Set the active cabin for vehicle entrance monitoring.
        
        Args:
            cabin_id: The cabin ID to set as active (e.g., "cabina-01")
            
        Returns:
            True if successful, False if cabin doesn't exist
        """
        should_notify = False
        with self._lock:
            if not self._multi_cabin_mode:
                self.logger.warning("Cannot set active cabin in single-cabin mode")
                return False
            
            if cabin_id not in self.cabins:
                self.logger.warning("Attempted to set invalid active cabin: %s (available: %s)", 
                                  cabin_id, ", ".join(self.cabins))
                return False
            
            if self._active_cabin != cabin_id:
                old_cabin = self._active_cabin
                self._active_cabin = cabin_id
                self.logger.info("Active cabin changed: %s -> %s", old_cabin, cabin_id)
                should_notify = True
            else:
                self.logger.info("Active cabin already set to %s (no change)", cabin_id)
        
        # Notify subscribers AFTER releasing the lock to avoid deadlock
        if should_notify:
            self._notify_subscribers()
        
        return True

    def snapshot(self, cabin_id: Optional[str] = None) -> Dict[str, Any]:
        """Get snapshot of presence state.
        
        Args:
            cabin_id: If provided and in multi-cabin mode, returns state for that cabin only.
                     If None in multi-cabin mode, returns state for active cabin (or all cabins if active not set).
                     In single-cabin mode, this parameter is ignored.
        """
        with self._lock:
            if self._multi_cabin_mode:
                if cabin_id:
                    # Return state for specific cabin
                    if cabin_id not in self._state:
                        return {"error": f"Cabin {cabin_id} not found"}
                    target_cabin = cabin_id
                else:
                    # Return state for active cabin (default behavior for vehicle entrance monitoring)
                    if self._active_cabin:
                        target_cabin = self._active_cabin
                        self.logger.debug("Using active cabin for snapshot: %s", target_cabin)
                    elif self.cabins:
                        # Fallback to first cabin if active not set
                        target_cabin = self.cabins[0]
                        self.logger.warning("No active cabin set, defaulting to %s", target_cabin)
                    else:
                        return {"error": "No cabins available"}
                
                # Return state for target cabin (formatted as single-cabin for frontend compatibility)
                if target_cabin not in self._state:
                    return {"error": f"Cabin {target_cabin} not found"}
                
                cabin_state = self._state[target_cabin]
                entry_present = bool(cabin_state["entry"]["present"])
                full_present = bool(cabin_state["full"]["present"])
                prev_entry, prev_full = cabin_state["previous"]
                
                state_info = self._determine_state(entry_present, full_present, prev_entry, prev_full)
                updated_at = None
                for ts in (cabin_state["entry"]["ts"], cabin_state["full"]["ts"], cabin_state.get("distance", {}).get("ts")):
                    if ts:
                        updated_at = max(updated_at or ts, ts)
                
                distance = cabin_state.get("distance", {})
                return {
                    "entry": {
                        "present": entry_present,
                        "ts": _iso(cabin_state["entry"]["ts"]),
                    },
                    "full": {
                        "present": full_present,
                        "ts": _iso(cabin_state["full"]["ts"]),
                    },
                    "distance": {
                        "from_mm": distance.get("from_mm"),
                        "to_mm": distance.get("to_mm"),
                        "ts": _iso(distance.get("ts")),
                    },
                    "occupied": full_present,
                    "state": state_info["state"],
                    "message": state_info["message"],
                    "status": self._status,
                    "status_detail": self._status_detail,
                    "connected": self._connected,
                    "updated_at": _iso(updated_at),
                }
            else:
                # Single-cabin mode (backward compatible)
                entry_present = bool(self._state["entry"]["present"])
                full_present = bool(self._state["full"]["present"])
                
                entry = {
                    "present": entry_present,
                    "ts": _iso(self._state["entry"]["ts"]),
                }
                full = {
                    "present": full_present,
                    "ts": _iso(self._state["full"]["ts"]),
                }
                distance = self._state.get("distance", {})
                updated_at = None
                for ts in (self._state["entry"]["ts"], self._state["full"]["ts"], distance.get("ts")):
                    if ts:
                        updated_at = max(updated_at or ts, ts)
                
                # Determine state and transition
                prev_entry, prev_full = self._previous_combined_state or (False, False)
                state_info = self._determine_state(entry_present, full_present, prev_entry, prev_full)
                
                return {
                    "entry": entry,
                    "full": full,
                    "distance": {
                        "from_mm": distance.get("from_mm"),
                        "to_mm": distance.get("to_mm"),
                        "ts": _iso(distance.get("ts")),
                    },
                    "occupied": full_present,
                    "state": state_info["state"],
                    "message": state_info["message"],
                    "status": self._status,
                    "status_detail": self._status_detail,
                    "connected": self._connected,
                    "updated_at": _iso(updated_at),
                }
    
    def _determine_state(self, entry_present: bool, full_present: bool, 
                        prev_entry: bool = False, prev_full: bool = False) -> Dict[str, str]:
        """Determine the current state and message based on sensor values and previous state."""
        # State 1: Both off -> Free
        if not entry_present and not full_present:
            state = "free"
            message = "Espacio libre"
        
        # State 2: Entry on, Full off -> Transitioning
        elif entry_present and not full_present:
            # Check if coming from both off (entering) or from both on (exiting)
            if not prev_entry and not prev_full:
                state = "transitioning"
                message = "Vehiculo ingresando..."
            elif prev_entry and prev_full:
                state = "transitioning"
                message = "Vehiculo saliendo..."
            else:
                # Maintain previous transition state if unclear
                state = "transitioning"
                message = "Vehiculo ingresando..." if not prev_entry else "Vehiculo saliendo..."
        
        # State 3: Both on -> Fully entered
        elif entry_present and full_present:
            state = "entered"
            message = "Vehiculo ingresado"
        
        # State 4: Entry off, Full on -> Shouldn't happen normally, treat as free
        else:
            state = "free"
            message = "Espacio libre"
        
        return {"state": state, "message": message}

    # Internals ----------------------------------------------------------------
    def _run(self) -> None:
        client = mqtt.Client(client_id=self.client_id, clean_session=True)
        if self.username:
            client.username_pw_set(self.username, self.password)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=10)

        retry_delay = 5
        while not self._stop_event.is_set():
            try:
                self._set_status("connecting", None)
                self.logger.info("Connecting to MQTT %s:%s as %s", self.broker, self.port, self.client_id)
                client.connect(self.broker, self.port, keepalive=30)
                client.loop_forever()
            except Exception as exc:  # network errors
                self.logger.exception("Presence MQTT error: %s", exc)
                self._set_status("error", str(exc))
                self._connected = False
                if self._stop_event.wait(timeout=retry_delay):
                    break
                continue

    def _on_connect(self, client, userdata, flags, rc):
        success = rc == 0
        self._connected = success
        if success:
            self._set_status("online", None)
            self.logger.info("Presence MQTT connected rc=%s", rc)
            
            if self._multi_cabin_mode:
                # Subscribe to all cabin topics
                for cabin in self.cabins:
                    # Cabin ID already includes "cabina-" prefix, use it directly
                    device_id = cabin
                    topic_entry = f"{self.topic_base}/{self.site}/{device_id}/presence/entry"
                    topic_full = f"{self.topic_base}/{self.site}/{device_id}/presence/full"
                    topic_distance = f"{self.topic_base}/{self.site}/{device_id}/distance/event"
                    topic_floor = f"{self.topic_base}/{self.site}/{device_id}/floor/reached"
                    topic_calib = f"{self.topic_base}/{self.site}/{device_id}/calibration/complete"
                    client.subscribe(topic_entry, qos=1)
                    client.subscribe(topic_full, qos=1)
                    client.subscribe(topic_distance, qos=0)  # Distance events are non-retained, QoS 0
                    client.subscribe(topic_floor, qos=1)  # Floor events
                    client.subscribe(topic_calib, qos=1)  # Calibration events
                    self.logger.info("Subscribed to %s, %s, %s, %s, and %s", 
                                   topic_entry, topic_full, topic_distance, topic_floor, topic_calib)
            else:
                # Single-cabin mode
                if self.topic_entry:
                    client.subscribe(self.topic_entry, qos=1)
                    self.logger.info("Subscribed to %s", self.topic_entry)
                if self.topic_full:
                    client.subscribe(self.topic_full, qos=1)
                    self.logger.info("Subscribed to %s", self.topic_full)
                # Subscribe to distance, floor, and calibration topics for single-cabin mode
                # Extract device ID from topic_entry or topic_full
                if self.topic_entry:
                    # Extract device from topic: parking/site/device/presence/entry
                    parts = self.topic_entry.split("/")
                    if len(parts) >= 3:
                        device_id = parts[2]
                        topic_distance = f"{self.topic_base}/{self.site}/{device_id}/distance/event"
                        topic_floor = f"{self.topic_base}/{self.site}/{device_id}/floor/reached"
                        topic_calib = f"{self.topic_base}/{self.site}/{device_id}/calibration/complete"
                        client.subscribe(topic_distance, qos=0)
                        client.subscribe(topic_floor, qos=1)
                        client.subscribe(topic_calib, qos=1)
                        self.logger.info("Subscribed to %s, %s, and %s", topic_distance, topic_floor, topic_calib)
        else:
            self._set_status("error", f"connect rc={rc}")
            self.logger.error("Presence MQTT failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if not self._stop_event.is_set():
            self._set_status("connecting", None)
            self.logger.warning("Presence MQTT disconnected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            self.logger.warning("Failed to parse MQTT message from topic %s", msg.topic)
            return

        sensor = payload.get("sensor")
        present = bool(payload.get("present"))
        ts = payload.get("ts") or time.time()
        device = payload.get("device", "")
        
        # Check if this is a distance message
        from_mm = payload.get("from_mm")
        to_mm = payload.get("to_mm")
        is_distance = from_mm is not None or to_mm is not None
        
        # Check if this is a floor/reached event
        is_floor_reached = "floor/reached" in msg.topic or payload.get("floor_level_mm") is not None
        
        # Check if this is a calibration/complete event
        is_calibration_complete = "calibration/complete" in msg.topic or payload.get("calibration_rounds") is not None

        self.logger.debug("MQTT message received topic=%s device=%s sensor=%s present=%s distance=%s floor=%s calib=%s", 
                         msg.topic, device, sensor, present, is_distance, is_floor_reached, is_calibration_complete)

        if self._multi_cabin_mode:
            # Extract cabin ID from device name or topic
            cabin_id = None
            if device.startswith("cabina-"):
                cabin_id = device  # Cabin ID already includes "cabina-" prefix
            else:
                # Try to extract from topic
                parts = msg.topic.split("/")
                if len(parts) >= 3:
                    device_part = parts[2]
                    if device_part.startswith("cabina-"):
                        cabin_id = device_part
            
            if cabin_id and cabin_id in self.cabins:
                # Handle floor/reached events
                if is_floor_reached:
                    distance_mm = payload.get("distance_mm")
                    floor_level_mm = payload.get("floor_level_mm")
                    self.logger.info("Floor reached event received cabin=%s distance_mm=%s floor_level_mm=%s ts=%s", 
                                   cabin_id, distance_mm, floor_level_mm, ts)
                    # Call registered callbacks
                    with self._callbacks_lock:
                        for callback in self._floor_reached_callbacks:
                            try:
                                callback(cabin_id, {
                                    "distance_mm": distance_mm,
                                    "floor_level_mm": floor_level_mm,
                                    "ts": ts
                                })
                            except Exception as e:
                                self.logger.error("Error in floor_reached callback: %s", e, exc_info=True)
                
                # Handle calibration/complete events
                elif is_calibration_complete:
                    floor_level_mm = payload.get("floor_level_mm")
                    calibration_rounds = payload.get("calibration_rounds")
                    min_distance_mm = payload.get("min_distance_mm")
                    max_distance_mm = payload.get("max_distance_mm")
                    self.logger.info("Calibration complete event received cabin=%s floor_level_mm=%s rounds=%s ts=%s", 
                                   cabin_id, floor_level_mm, calibration_rounds, ts)
                    # Call registered callbacks
                    with self._callbacks_lock:
                        for callback in self._calibration_complete_callbacks:
                            try:
                                callback(cabin_id, {
                                    "floor_level_mm": floor_level_mm,
                                    "calibration_rounds": calibration_rounds,
                                    "min_distance_mm": min_distance_mm,
                                    "max_distance_mm": max_distance_mm,
                                    "ts": ts
                                })
                            except Exception as e:
                                self.logger.error("Error in calibration_complete callback: %s", e, exc_info=True)
                
                # Handle distance messages
                elif is_distance or "distance" in msg.topic:
                    self.logger.info("Distance event received cabin=%s from_mm=%s to_mm=%s ts=%s topic=%s", 
                                   cabin_id, from_mm, to_mm, ts, msg.topic)
                    self._update_distance_multi(cabin_id, from_mm, to_mm, ts)
                # Determine sensor type for presence messages
                elif sensor == "ir1" or "entry" in msg.topic:
                    self._update_state_multi(cabin_id, "entry", present, ts)
                elif sensor == "ir2" or "full" in msg.topic:
                    self._update_state_multi(cabin_id, "full", present, ts)
            else:
                self.logger.debug("Ignoring message for unknown cabin: %s", cabin_id)
        else:
            # Single-cabin mode (backward compatible)
            # Handle floor/reached events
            if is_floor_reached:
                distance_mm = payload.get("distance_mm")
                floor_level_mm = payload.get("floor_level_mm")
                self.logger.info("Floor reached event received distance_mm=%s floor_level_mm=%s ts=%s", 
                               distance_mm, floor_level_mm, ts)
                # Call registered callbacks (use device ID as cabin_id for single-cabin mode)
                cabin_id = device if device else "cabina-01"
                with self._callbacks_lock:
                    for callback in self._floor_reached_callbacks:
                        try:
                            callback(cabin_id, {
                                "distance_mm": distance_mm,
                                "floor_level_mm": floor_level_mm,
                                "ts": ts
                            })
                        except Exception as e:
                            self.logger.error("Error in floor_reached callback: %s", e, exc_info=True)
            
            # Handle calibration/complete events
            elif is_calibration_complete:
                floor_level_mm = payload.get("floor_level_mm")
                calibration_rounds = payload.get("calibration_rounds")
                min_distance_mm = payload.get("min_distance_mm")
                max_distance_mm = payload.get("max_distance_mm")
                self.logger.info("Calibration complete event received floor_level_mm=%s rounds=%s ts=%s", 
                               floor_level_mm, calibration_rounds, ts)
                # Call registered callbacks
                cabin_id = device if device else "cabina-01"
                with self._callbacks_lock:
                    for callback in self._calibration_complete_callbacks:
                        try:
                            callback(cabin_id, {
                                "floor_level_mm": floor_level_mm,
                                "calibration_rounds": calibration_rounds,
                                "min_distance_mm": min_distance_mm,
                                "max_distance_mm": max_distance_mm,
                                "ts": ts
                            })
                        except Exception as e:
                            self.logger.error("Error in calibration_complete callback: %s", e, exc_info=True)
            
            # Handle distance messages
            elif is_distance or "distance" in msg.topic:
                self.logger.info("Distance event received from_mm=%s to_mm=%s ts=%s topic=%s", 
                               from_mm, to_mm, ts, msg.topic)
                self._update_distance(from_mm, to_mm, ts)
            # IR1 (entry sensor): detects when vehicle starts entering the cabin
            elif msg.topic == self.topic_entry or sensor == "ir1":
                self._update_state("entry", present, ts)
            # IR2 (full sensor): detects when vehicle is fully entered into the cabin
            elif msg.topic == self.topic_full or sensor == "ir2":
                self._update_state("full", present, ts)

    def _update_state(self, key: str, present: bool, ts: float) -> None:
        """Update state for single-cabin mode."""
        with self._lock:
            self._state[key] = {"present": present, "ts": ts}
            # Update previous combined state
            if key == "entry":
                entry_present = present
                full_present = bool(self._state["full"]["present"])
            else:  # key == "full"
                entry_present = bool(self._state["entry"]["present"])
                full_present = present
            self._previous_combined_state = (entry_present, full_present)
        self.logger.debug("Presence update %s present=%s ts=%s", key, present, ts)
        # Notify all subscribers of state change
        self._notify_subscribers()
    
    def _update_state_multi(self, cabin_id: str, key: str, present: bool, ts: float) -> None:
        """Update state for multi-cabin mode."""
        with self._lock:
            if cabin_id not in self._state:
                self._state[cabin_id] = {
                    "entry": {"present": False, "ts": None},
                    "full": {"present": False, "ts": None},
                    "previous": (False, False),
                    "distance": {"from_mm": None, "to_mm": None, "ts": None},
                }
            
            self._state[cabin_id][key] = {"present": present, "ts": ts}
            # Update previous combined state for this cabin
            entry_present = bool(self._state[cabin_id]["entry"]["present"])
            full_present = bool(self._state[cabin_id]["full"]["present"])
            self._state[cabin_id]["previous"] = (entry_present, full_present)
        self.logger.debug("Presence update cabin=%s %s present=%s ts=%s", cabin_id, key, present, ts)
        # Notify all subscribers of state change
        self._notify_subscribers()
    
    def _update_distance(self, from_mm: Optional[int], to_mm: Optional[int], ts: float) -> None:
        """Update distance for single-cabin mode."""
        with self._lock:
            if "distance" not in self._state:
                self._state["distance"] = {"from_mm": None, "to_mm": None, "ts": None}
            self._state["distance"] = {
                "from_mm": from_mm,
                "to_mm": to_mm,
                "ts": ts,
            }
        self.logger.debug("Distance update from_mm=%s to_mm=%s ts=%s", from_mm, to_mm, ts)
        # Notify all subscribers of state change
        self._notify_subscribers()
    
    def _update_distance_multi(self, cabin_id: str, from_mm: Optional[int], to_mm: Optional[int], ts: float) -> None:
        """Update distance for multi-cabin mode."""
        with self._lock:
            if cabin_id not in self._state:
                self._state[cabin_id] = {
                    "entry": {"present": False, "ts": None},
                    "full": {"present": False, "ts": None},
                    "previous": (False, False),
                    "distance": {"from_mm": None, "to_mm": None, "ts": None},
                }
            self._state[cabin_id]["distance"] = {
                "from_mm": from_mm,
                "to_mm": to_mm,
                "ts": ts,
            }
        self.logger.debug("Distance update cabin=%s from_mm=%s to_mm=%s ts=%s", cabin_id, from_mm, to_mm, ts)
        # Notify all subscribers of state change
        self._notify_subscribers()
    
    def _notify_subscribers(self) -> None:
        """Send current snapshot to all subscribed SSE clients."""
        snapshot = self.snapshot()
        snapshot_json = json.dumps(snapshot)
        
        with self._subscribers_lock:
            # Create a copy of the list to avoid holding lock while iterating
            subscribers = list(self._subscribers)
        
        # Send to all subscribers, removing dead ones
        dead_subscribers = []
        for client_queue in subscribers:
            try:
                client_queue.put_nowait(snapshot_json)
            except queue.Full:
                # Queue is full, client might be disconnected, mark for removal
                dead_subscribers.append(client_queue)
            except Exception as e:
                self.logger.warning("Error notifying subscriber: %s", e)
                dead_subscribers.append(client_queue)
        
        # Remove dead subscribers
        if dead_subscribers:
            with self._subscribers_lock:
                for dead in dead_subscribers:
                    try:
                        self._subscribers.remove(dead)
                    except ValueError:
                        pass

    def _set_status(self, status: str, detail: Optional[str]) -> None:
        with self._lock:
            self._status = status
            self._status_detail = detail
        # Notify subscribers of status change (outside lock to avoid deadlock)
        self._notify_subscribers()


def presence_service_from_env(logger: Optional[logging.Logger] = None) -> PresenceService:
    return PresenceService.from_env(logger=logger)
