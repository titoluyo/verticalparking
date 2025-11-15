"""Background MQTT presence consumer used by the kiosk UI."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or fallback


def _iso(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class PresenceService:
    """Subscribes to retained presence topics and stores the latest state in memory."""

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
        self._status = "initializing"
        self._status_detail: Optional[str] = None
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
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
            "Starting presence watcher broker=%s topics entry=%s full=%s",
            self.broker,
            self.topic_entry,
            self.topic_full,
        )
        self._thread = threading.Thread(target=self._run, name="presence-mqtt", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "present": bool(self._state["entry"]["present"]),
                "ts": _iso(self._state["entry"]["ts"]),
            }
            full = {
                "present": bool(self._state["full"]["present"]),
                "ts": _iso(self._state["full"]["ts"]),
            }
            updated_at = None
            for ts in (self._state["entry"]["ts"], self._state["full"]["ts"]):
                if ts:
                    updated_at = max(updated_at or ts, ts)
            return {
                "entry": entry,
                "full": full,
                "occupied": bool(self._state["full"]["present"]),
                "status": self._status,
                "status_detail": self._status_detail,
                "connected": self._connected,
                "updated_at": _iso(updated_at),
            }

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
            return

        sensor = payload.get("sensor")
        present = bool(payload.get("present"))
        ts = payload.get("ts") or time.time()

        if msg.topic == self.topic_entry or sensor == "ir1":
            self._update_state("entry", present, ts)
        elif msg.topic == self.topic_full or sensor == "ir2":
            self._update_state("full", present, ts)

    def _update_state(self, key: str, present: bool, ts: float) -> None:
        with self._lock:
            self._state[key] = {"present": present, "ts": ts}
        self.logger.debug("Presence update %s present=%s ts=%s", key, present, ts)

    def _set_status(self, status: str, detail: Optional[str]) -> None:
        with self._lock:
            self._status = status
            self._status_detail = detail


def presence_service_from_env(logger: Optional[logging.Logger] = None) -> PresenceService:
    return PresenceService.from_env(logger=logger)
