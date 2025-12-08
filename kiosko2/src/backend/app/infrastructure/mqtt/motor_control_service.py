"""MQTT-based motor control service."""

import json
import logging
import threading
import time
from typing import Optional, Dict

import paho.mqtt.client as mqtt

from ...core.interfaces.services import IMotorControlService


class MotorControlService(IMotorControlService):
    """MQTT-based motor control service."""
    
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        site: str = "garage-01",
        topic_base: str = "parking",
        logger: Optional[logging.Logger] = None,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.site = site
        self.topic_base = topic_base
        self.logger = logger or logging.getLogger(__name__)
        
        self._calibration_state: Dict[str, bool] = {}
        self._lock = threading.Lock()
    
    def _send_mqtt_message(self, topic: str, payload: str, qos: int = 1) -> bool:
        """Send MQTT message."""
        try:
            client = mqtt.Client(client_id=f"motor-control-{int(time.time())}")
            if self.username and self.password:
                client.username_pw_set(self.username, self.password)
            
            client.connect(self.broker, self.port, 60)
            client.publish(topic, payload, qos=qos, retain=False)
            client.disconnect()
            
            self.logger.info(f"Sent MQTT: {topic} -> {payload}")
            return True
        except Exception as e:
            self.logger.error(f"MQTT send error: {e}")
            return False
    
    def start_motor(self, cabin_id: Optional[str] = None) -> bool:
        """Start the motor."""
        topic = f"{self.topic_base}/{self.site}/motor"
        return self._send_mqtt_message(topic, "ON")
    
    def stop_motor(self, cabin_id: Optional[str] = None) -> bool:
        """Stop the motor."""
        topic = f"{self.topic_base}/{self.site}/motor"
        return self._send_mqtt_message(topic, "OFF")
    
    def send_calibration_command(self, cabin_id: str, command: str) -> bool:
        """Send calibration command."""
        topic = f"{self.topic_base}/{self.site}/{cabin_id}/cmd"
        
        if command.lower() == "start":
            payload = json.dumps({"start_calibration": True})
            with self._lock:
                self._calibration_state[cabin_id] = True
        elif command.lower() == "stop":
            payload = json.dumps({"stop_calibration": True})
            with self._lock:
                self._calibration_state[cabin_id] = False
        else:
            self.logger.error(f"Invalid calibration command: {command}")
            return False
        
        return self._send_mqtt_message(topic, payload)
    
    def is_calibrating(self, cabin_id: str) -> bool:
        """Check if cabin is calibrating."""
        with self._lock:
            return self._calibration_state.get(cabin_id, False)
