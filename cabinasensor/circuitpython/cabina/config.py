# config.py
import os, wifi

def _mac_suffix():
    m = wifi.radio.mac_address
    return f"{m[-3]:02X}{m[-2]:02X}{m[-1]:02X}"

SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PWD  = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if not SSID or not PWD:
    raise RuntimeError("Missing Wi-Fi credentials in settings.toml")

BROKER   = os.getenv("MQTT_BROKER") or "10.30.136.215"
PORT     = int(os.getenv("MQTT_PORT") or "1883")
USER     = os.getenv("MQTT_USER") or None
PASSWORD = os.getenv("MQTT_PASSWORD") or None

SITE_ID   = os.getenv("SITE_ID")   or "default-site"
DEVICE_ID = os.getenv("DEVICE_ID") or f"esp32c6-{_mac_suffix()}"
ROOT      = os.getenv("TOPIC_BASE") or "parking"

PUB_INTERVAL = max(1, int(os.getenv("PUB_INTERVAL_SEC") or "10"))
SAMPLE_PERIOD = float(os.getenv("SAMPLE_PERIOD_SEC") or "0.05")   # sensor poll rate
IR_PULLUPS = (os.getenv("IR_PULLUPS") != "0")

# Topics
TOP_DEV   = f"{ROOT}/{SITE_ID}/{DEVICE_ID}"
TOP_TELE  = f"{TOP_DEV}/telemetry"
TOP_EVENT = f"{TOP_DEV}/event"
TOP_CMD   = f"{TOP_DEV}/cmd"
TOP_STAT  = f"{TOP_DEV}/status"

TOP_EVENT_IR1 = f"{TOP_DEV}/presence/entry"
TOP_EVENT_IR2 = f"{TOP_DEV}/presence/full"
TOP_EVENT_DISTANCE = f"{TOP_DEV}/distance/event"

# Retain presence state so subscribers can read the latest value on connect
PRESENCE_RETAIN = (os.getenv("PRESENCE_RETAIN") != "0")  # default True