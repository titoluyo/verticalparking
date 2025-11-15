# mqtt_client.py
import time, json
from adafruit_minimqtt import adafruit_minimqtt as MQTT

class MqttClient:
    def __init__(self, pool, cfg, on_cmd=None):
        self.cfg = cfg
        self.on_cmd = on_cmd
        # Handle old/new MiniMQTT signatures
        try:
            self.client = MQTT.MQTT(
                broker=cfg.BROKER, port=cfg.PORT, username=cfg.USER, password=cfg.PASSWORD,
                socket_pool=pool, is_ssl=False, keep_alive=30
            )
        except TypeError:
            MQTT.set_socket(pool, None)
            self.client = MQTT.MQTT(
                broker=cfg.BROKER, port=cfg.PORT, username=cfg.USER, password=cfg.PASSWORD,
                is_ssl=False, keep_alive=30
            )

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe

        # LWT
        self.client.will_set(cfg.TOP_STAT, json.dumps({
            "site": cfg.SITE_ID, "device": cfg.DEVICE_ID, "status": "offline"
        }), retain=True)

    # Public API
    def connect(self):
        while True:
            try:
                print(f"Connecting MQTT {self.cfg.BROKER}:{self.cfg.PORT} as {self.cfg.DEVICE_ID} ...")
                self.client.connect()
                return
            except Exception as e:
                print("MQTT connect error:", repr(e))
                time.sleep(3)

    def loop(self, timeout=1):
        self.client.loop(timeout=timeout)

    def publish_json(self, topic, obj, retain=False, qos=0):
        self.client.publish(topic, json.dumps(obj), retain=retain, qos=qos)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic, qos=qos)

    # Internals
    def _on_connect(self, c, u, flags, rc):
        print("MQTT connected:", rc)
        self.subscribe(self.cfg.TOP_CMD, qos=0)
        self.publish_json(self.cfg.TOP_STAT, {
            "site": self.cfg.SITE_ID, "device": self.cfg.DEVICE_ID,
            "ip": str(__import__('wifi').radio.ipv4_address),
            "status": "online", "ts": time.time()
        }, retain=True)

    def _on_disconnect(self, c, u, rc):
        print("MQTT disconnected:", rc)

    def _on_subscribe(self, c, u, topic, qos):
        print("Subscribed:", topic, qos)

    def _on_message(self, c, topic, msg):
        if topic == self.cfg.TOP_CMD and self.on_cmd:
            try:
                self.on_cmd(msg)
            except Exception as e:
                print("cmd error:", repr(e))
