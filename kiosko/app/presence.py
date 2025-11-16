"""Background MQTT presence consumer used by the kiosk UI."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple

import paho.mqtt.client as mqtt


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or fallback


def _iso(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class PresenceService:
    """Subscribes to retained presence topics and stores the latest state in memory.
    
    Monitors two IR sensors:
    - Entry sensor (IR1): Detects when a vehicle starts entering the cabin
    - Full sensor (IR2): Detects when a vehicle is fully entered into the cabin
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topic_entry: Optional[str] = None,
        topic_full: Optional[str] = None,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_entry = topic_entry
        self.topic_full = topic_full
        self.client_id = client_id or f"kiosko-presence-{int(time.time())}"
        self.logger = logger or logging.getLogger(__name__)

        self._lock = threading.Lock()
        self._state: Dict[str, Dict[str, Any]] = {
            "entry": {"present": False, "ts": None},
            "full": {"present": False, "ts": None},
        }
        # Track previous combined state to detect transitions
        self._previous_combined_state: Optional[Tuple[bool, bool]] = None  # (entry, full)
        self._status = "initializing"
        self._status_detail: Optional[str] = None
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # SSE subscribers: list of queues for each connected client
        self._subscribers: list[queue.Queue] = []
        self._subscribers_lock = threading.Lock()
        self.logger.debug("PresenceService initialized client_id=%s", self.client_id)

    # Factory -----------------------------------------------------------------
    @classmethod
    def from_env(cls, logger: Optional[logging.Logger] = None) -> "PresenceService":
        broker = _env("KIOSKO_MQTT_HOST", _env("MQTT_BROKER", "127.0.0.1"))
        port = int(_env("KIOSKO_MQTT_PORT", _env("MQTT_PORT", "1883")))
        username = _env("KIOSKO_MQTT_USER", _env("MQTT_USER"))
        password = _env("KIOSKO_MQTT_PASSWORD", _env("MQTT_PASSWORD"))

        topic_base = _env("KIOSKO_TOPIC_BASE", _env("TOPIC_BASE", "parking"))
        site = _env("KIOSKO_SITE_ID", _env("SITE_ID", "default-site"))
        device = _env("KIOSKO_DEVICE_ID", _env("DEVICE_ID", "esp32-sensor"))

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

    # Public API ---------------------------------------------------------------
    def start(self) -> None:
        self.logger.debug("PresenceService start called")
        if self._thread and self._thread.is_alive():
            self.logger.warning("PresenceService already started")
            return
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

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
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
            updated_at = None
            for ts in (self._state["entry"]["ts"], self._state["full"]["ts"]):
                if ts:
                    updated_at = max(updated_at or ts, ts)
            
            # Determine state and transition
            state_info = self._determine_state(entry_present, full_present)
            
            return {
                "entry": entry,
                "full": full,
                "occupied": full_present,
                "state": state_info["state"],
                "message": state_info["message"],
                "status": self._status,
                "status_detail": self._status_detail,
                "connected": self._connected,
                "updated_at": _iso(updated_at),
            }
    
    def _determine_state(self, entry_present: bool, full_present: bool) -> Dict[str, str]:
        """Determine the current state and message based on sensor values and previous state."""
        prev_entry, prev_full = self._previous_combined_state or (False, False)
        
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
        
        # Update previous combined state for next call
        self._previous_combined_state = (entry_present, full_present)
        
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
            if self.topic_entry:
                client.subscribe(self.topic_entry, qos=1)
                self.logger.info("Subscribed to %s", self.topic_entry)
            if self.topic_full:
                client.subscribe(self.topic_full, qos=1)
                self.logger.info("Subscribed to %s", self.topic_full)
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

        self.logger.info("MQTT message received topic=%s sensor=%s present=%s", msg.topic, sensor, present)

        # IR1 (entry sensor): detects when vehicle starts entering the cabin
        if msg.topic == self.topic_entry or sensor == "ir1":
            self._update_state("entry", present, ts)
        # IR2 (full sensor): detects when vehicle is fully entered into the cabin
        elif msg.topic == self.topic_full or sensor == "ir2":
            self._update_state("full", present, ts)

    def _update_state(self, key: str, present: bool, ts: float) -> None:
        with self._lock:
            self._state[key] = {"present": present, "ts": ts}
        self.logger.debug("Presence update %s present=%s ts=%s", key, present, ts)
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
