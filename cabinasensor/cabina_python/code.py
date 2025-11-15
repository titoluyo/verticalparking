# code.py
import time, json
import config
from net import connect_wifi, socket_pool
from mqtt_client import MqttClient
from sensors import Sensors
import wifi

radio = connect_wifi()
pool = socket_pool()
sensors = Sensors(use_s3=True)

# Command handler (only updates state; keep it short)
def handle_cmd(msg):
    if msg == "ping":
        mqtt.publish_json(config.TOP_EVENT, {"type":"pong","ts":time.time(),"device":config.DEVICE_ID})
        return
    try:
        obj = json.loads(msg)
        if "pub_interval" in obj:
            global PUB_INTERVAL
            PUB_INTERVAL = max(1, int(obj["pub_interval"]))
            mqtt.publish_json(config.TOP_EVENT, {"type":"pub_interval_set","value":PUB_INTERVAL,"ts":time.time()})
    except Exception:
        pass

mqtt = MqttClient(pool, config, on_cmd=handle_cmd)
mqtt.connect()

PUB_INTERVAL = config.PUB_INTERVAL
last_pub = 0
last_sample = 0
SAMPLE_PERIOD = config.SAMPLE_PERIOD

while True:
    try:
        mqtt.loop(timeout=1)
        now = time.monotonic()

        if now - last_sample >= SAMPLE_PERIOD:
            print("Sampling sensors...")
            for ev in sensors.edge_events(dist_threshold=20):
                # Common metadata
                base = {
                    "site": config.SITE_ID,
                    "device": config.DEVICE_ID,
                    "ts": time.time()
                }

                if ev["type"] == "ir1":
                    payload = base.copy()
                    payload["sensor"] = "ir1"
                    payload["present"] = bool(ev["value"])
                    mqtt.publish_json(config.TOP_EVENT_IR1, payload,
                                    retain=config.PRESENCE_RETAIN, qos=1)

                elif ev["type"] == "ir2":
                    payload = base.copy()
                    payload["sensor"] = "ir2"
                    payload["present"] = bool(ev["value"])
                    mqtt.publish_json(config.TOP_EVENT_IR2, payload,
                                    retain=config.PRESENCE_RETAIN, qos=1)

                elif ev["type"] == "distance_change":
                    payload = base.copy()
                    payload["from_mm"] = ev["from"]
                    payload["to_mm"] = ev["to"]
                    mqtt.publish_json(config.TOP_EVENT_DISTANCE, payload,
                                    retain=False, qos=0)

            last_sample = now


        if now - last_pub >= PUB_INTERVAL:
            t = sensors.telemetry()
            t.update({
                "site": config.SITE_ID,
                "device": config.DEVICE_ID,
                "ip": str(radio.ipv4_address),
                "ts": time.time()
            })
            #mqtt.publish_json(config.TOP_TELE, t)
            #print("[TX]", config.TOP_TELE, t)
            last_pub = now

    except (OSError, RuntimeError) as e:
        print("Loop error:", repr(e))
        # (optional) Reconnect Wi-Fi if needed, then reconnect MQTT
        try:
            if not wifi.radio.ipv4_address:
                print("Reconnecting Wi-Fi...")
                wifi.radio.connect(config.SSID, config.PWD)
                print("Wi-Fi reconnected:", wifi.radio.ipv4_address)
        except Exception as we:
            print("Wi-Fi reconnection failed:", repr(we))
            time.sleep(3)
            continue
        mqtt.connect()
