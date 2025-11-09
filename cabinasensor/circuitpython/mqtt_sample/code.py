import os
import time
import wifi
import socketpool
from adafruit_minimqtt import adafruit_minimqtt as MQTT

# --- Wi-Fi from settings.toml ---
SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PWD  = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if not SSID or not PWD:
    raise RuntimeError("Missing Wi-Fi creds in settings.toml")

print("Connecting Wi-Fi...")
wifi.radio.connect(SSID, PWD)
print("Wi-Fi OK, IP:", wifi.radio.ipv4_address)

# --- MQTT broker settings ---
BROKER   = os.getenv("MQTT_BROKER") or "10.30.136.215"
PORT     = int(os.getenv("MQTT_PORT") or "1883")
USER     = os.getenv("MQTT_USER") or None
PASSWORD = os.getenv("MQTT_PASSWORD") or None

PUB_TOPIC  = "lab/esp32c6/out"
SUB_TOPIC  = "lab/esp32c6/in"
STATUS_T   = "lab/esp32c6/status"   # LWT topic

pool = socketpool.SocketPool(wifi.radio)

# Some MiniMQTT builds want set_socket() instead of socket_pool arg.
# The following works for both: try new style first, else fall back.
def make_client():
    try:
        # Newer API: pass socket_pool to constructor
        return MQTT.MQTT(
            broker=BROKER,
            port=PORT,
            username=USER,
            password=PASSWORD,
            socket_pool=pool,
            is_ssl=False,
            keep_alive=30,
        )
    except TypeError:
        # Older API: set socket globally, then construct without socket_pool
        MQTT.set_socket(pool, None)
        return MQTT.MQTT(
            broker=BROKER,
            port=PORT,
            username=USER,
            password=PASSWORD,
            is_ssl=False,
            keep_alive=30,
        )

mqtt = make_client()

# --- Callbacks ---
def handle_connect(client, userdata, flags, rc):
    print("MQTT connected, rc:", rc)
    client.subscribe(SUB_TOPIC, qos=0)
    client.publish(STATUS_T, "online", retain=True)

def handle_disconnect(client, userdata, rc):
    print("MQTT disconnected, rc:", rc)

def handle_message(client, topic, msg):
    print(f"[RX] {topic}: {msg}")
    if topic == SUB_TOPIC:
        client.publish(PUB_TOPIC, f"echo: {msg}")

def handle_subscribe(client, userdata, topic, granted_qos):
    print(f"Subscribed to {topic} with QoS {granted_qos}")

mqtt.on_connect = handle_connect
mqtt.on_disconnect = handle_disconnect
mqtt.on_message = handle_message
mqtt.on_subscribe = handle_subscribe

# Set Last Will (constructor doesn’t accept will_* in your version)
mqtt.will_set(STATUS_T, "offline", qos=0, retain=True)

def connect_mqtt():
    while True:
        try:
            print(f"Connecting MQTT {BROKER}:{PORT} ...")
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
        if now - last_pub >= 5:
            count += 1
            payload = f"hello #{count} from ESP32-C6 @ {wifi.radio.ipv4_address}"
            print("[TX]", PUB_TOPIC, payload)
            mqtt.publish(PUB_TOPIC, payload, retain=False, qos=0)
            last_pub = now
    except (OSError, RuntimeError) as e:
        print("Loop error:", repr(e))
        # Reconnect Wi-Fi if needed
        try:
            if not wifi.radio.ipv4_address:
                print("Reconnecting Wi-Fi...")
                wifi.radio.connect(SSID, PWD)
                print("Wi-Fi reconnected:", wifi.radio.ipv4_address)
        except Exception as we:
            print("Wi-Fi reconnection failed:", repr(we))
            time.sleep(3)
            continue
        # Reconnect MQTT
        connect_mqtt()
