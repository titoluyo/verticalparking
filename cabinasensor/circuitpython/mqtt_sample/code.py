import os, time, json
import wifi, socketpool
from adafruit_minimqtt import adafruit_minimqtt as MQTT

# ---- Wi-Fi ----
SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PWD  = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if not SSID or not PWD:
    raise RuntimeError("Missing Wi-Fi creds in settings.toml")
print("Connecting Wi-Fi...")
wifi.radio.connect(SSID, PWD)
print("Wi-Fi OK, IP:", wifi.radio.ipv4_address)

# ---- Broker ----
BROKER   = os.getenv("MQTT_BROKER") or "10.30.136.215"
PORT     = int(os.getenv("MQTT_PORT") or "1883")
USER     = os.getenv("MQTT_USER") or None
PASSWORD = os.getenv("MQTT_PASSWORD") or None

# ---- Identity & topics ----
def mac_suffix():
    m = wifi.radio.mac_address
    return f"{m[-3]:02X}{m[-2]:02X}{m[-1]:02X}"

SITE_ID   = os.getenv("SITE_ID")   or "default-site"
DEVICE_ID = os.getenv("DEVICE_ID") or f"esp32c6-{mac_suffix()}"
ROOT      = os.getenv("TOPIC_BASE") or "parking"

# topic scheme:
#   {ROOT}/{SITE_ID}/{DEVICE_ID}/telemetry
#   {ROOT}/{SITE_ID}/{DEVICE_ID}/cmd
#   {ROOT}/{SITE_ID}/{DEVICE_ID}/status
TOP_DEV = f"{ROOT}/{SITE_ID}/{DEVICE_ID}"
TOP_TELE = f"{TOP_DEV}/telemetry"
TOP_CMD  = f"{TOP_DEV}/cmd"
TOP_STAT = f"{TOP_DEV}/status"

PUB_INTERVAL = int(os.getenv("PUB_INTERVAL_SEC") or "5")

# ---- MQTT client ----
pool = socketpool.SocketPool(wifi.radio)

def make_client():
    try:
        return MQTT.MQTT(
            broker=BROKER, port=PORT, username=USER, password=PASSWORD,
            socket_pool=pool, is_ssl=False, keep_alive=30
        )
    except TypeError:
        MQTT.set_socket(pool, None)
        return MQTT.MQTT(
            broker=BROKER, port=PORT, username=USER, password=PASSWORD,
            is_ssl=False, keep_alive=30
        )

mqtt = make_client()

def on_connect(client, userdata, flags, rc):
    print("MQTT connected:", rc)
    client.subscribe(TOP_CMD, qos=0)
    # Birth message (retained)
    birth = {
        "site": SITE_ID,
        "device": DEVICE_ID,
        "ip": str(wifi.radio.ipv4_address),
        "status": "online",
        "ts": time.time(),
    }
    client.publish(TOP_STAT, json.dumps(birth), retain=True)

def on_message(client, topic, msg):
    print(f"[RX] {topic}: {msg}")
    # minimal command handler demo
    try:
        if topic == TOP_CMD and msg == "ping":
            client.publish(TOP_TELE, json.dumps({"device": DEVICE_ID, "pong": True, "ts": time.time()}))
    except Exception as e:
        print("cmd error:", e)

def on_disconnect(client, userdata, rc):
    print("MQTT disconnected:", rc)

def on_subscribe(client, userdata, topic, qos):
    print("Subscribed:", topic, qos)

mqtt.on_connect = on_connect
mqtt.on_message = on_message
mqtt.on_disconnect = on_disconnect
mqtt.on_subscribe = on_subscribe
# Will (retained): broker publishes if we drop unexpectedly
mqtt.will_set(TOP_STAT, json.dumps({"site": SITE_ID, "device": DEVICE_ID, "status": "offline"}), retain=True)

def connect_mqtt():
    while True:
        try:
            print(f"Connecting MQTT {BROKER}:{PORT} as {DEVICE_ID} ...")
            mqtt.connect()
            return
        except Exception as e:
            print("MQTT connect error:", repr(e))
            time.sleep(3)

connect_mqtt()

last_pub = 0
count = 0
while True:
    try:
        mqtt.loop(timeout=1)
        now = time.monotonic()
        if now - last_pub >= PUB_INTERVAL:
            count += 1
            payload = {
                "site": SITE_ID,
                "device": DEVICE_ID,
                "seq": count,
                "ip": str(wifi.radio.ipv4_address),
                "ts": time.time(),
                # add real sensor fields here, e.g. "encoder": value, "door": "open"
            }
            mqtt.publish(TOP_TELE, json.dumps(payload), retain=False, qos=0)
            print("[TX]", TOP_TELE, payload)
            last_pub = now
    except (OSError, RuntimeError) as e:
        print("Loop error:", repr(e))
        # optional: re-connect Wi-Fi here if needed, then:
        connect_mqtt()
