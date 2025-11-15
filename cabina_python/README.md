# Cabina Python - ESP32-S3 Sensor Firmware

CircuitPython firmware for ESP32-S3 and ESP32-C6 devices that monitors parking sensors and publishes presence data via MQTT. This firmware runs on the embedded sensor hardware in the parking cabina.

## Overview

This firmware continuously monitors three sensors:
- **IR1 (Entry Sensor)**: Detects vehicles at the parking entry point
- **IR2 (Full Sensor)**: Detects if the parking space is occupied
- **VL53L0X (Distance Sensor)**: Time-of-flight distance measurement

The firmware uses edge detection to publish MQTT messages only when sensor states change, reducing network traffic and providing real-time event notifications.

## Project Structure

```
cabina_python/
├── code.py              # Main entry point (CircuitPython auto-runs this)
├── config.py            # Configuration and topic definitions
├── sensors.py           # Sensor hardware interface and edge detection
├── mqtt_client.py       # MQTT client wrapper
├── net.py               # Wi-Fi connection management
├── settings.toml        # Wi-Fi and MQTT credentials (edit this!)
├── lib/                 # CircuitPython libraries
│   ├── adafruit_vl53l0x.mpy
│   ├── adafruit_minimqtt/
│   └── ...
└── tools/               # Development tools (see tools/README.md)
    ├── sync_to_esp32.py
    ├── monitor.py
    └── ...
```

## Hardware Requirements

- **ESP32-S3** or **ESP32-C6** development board
- **VL53L0X** time-of-flight distance sensor (I2C)
- **2x IR sensors** (digital inputs)
- CircuitPython firmware installed on the ESP32

### Pin Connections

**ESP32-S3:**
- IR1: GPIO2
- IR2: GPIO3
- VL53L0X SCL: GPIO9
- VL53L0X SDA: GPIO8

**ESP32-C6:**
- IR1: GPIO2
- IR2: GPIO3
- VL53L0X SCL: GPIO15
- VL53L0X SDA: GPIO14

## Installation

### 1. Install CircuitPython

1. Download CircuitPython firmware for your board:
   - [ESP32-S3](https://circuitpython.org/board/adafruit_feather_esp32s3/)
   - [ESP32-C6](https://circuitpython.org/board/adafruit_feather_esp32c6/)

2. Put board in bootloader mode (hold BOOT, press RESET, release BOOT)

3. Copy `.uf2` file to the `FTHRS3BOOT` or `FTHRC6BOOT` drive

4. Board will reboot and show `CIRCUITPY` drive

### 2. Install Libraries

1. Download [CircuitPython Library Bundle](https://circuitpython.org/libraries)

2. Copy required libraries to `CIRCUITPY/lib/`:
   - `adafruit_vl53l0x.mpy`
   - `adafruit_minimqtt/` (entire folder)
   - `adafruit_connection_manager.mpy`
   - `adafruit_ticks.mpy`

### 3. Deploy Code

**Option A: Manual Copy**
- Copy all `.py` files from `cabina_python/` to `CIRCUITPY/`
- Copy `settings.toml` to `CIRCUITPY/`

**Option B: Use Sync Tool (Recommended)**
```bash
cd tools
python sync_to_esp32.py
```

See `tools/README.md` for detailed instructions.

## Configuration

### settings.toml

Edit `settings.toml` on the CIRCUITPY drive with your credentials:

```toml
CIRCUITPY_WIFI_SSID = "YourWiFiNetwork"
CIRCUITPY_WIFI_PASSWORD = "YourWiFiPassword"

MQTT_BROKER = "10.21.247.223"
MQTT_PORT = "1883"
MQTT_USER = ""          # Leave empty if no auth
MQTT_PASSWORD = ""      # Leave empty if no auth

SITE_ID = "garage-01"
DEVICE_ID = "cabin-A01"
TOPIC_BASE = "parking"

PUB_INTERVAL_SEC = "5"
IR_PULLUPS = "1"
PRESENCE_RETAIN = "1"
```

### Environment Variables

The firmware reads configuration from `settings.toml` via `os.getenv()`. All settings can be overridden by editing `settings.toml`.

## MQTT Topics

### Published Topics

The firmware publishes to these topics:

1. **Presence Events** (retained, QoS 1):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/entry` - IR1 state changes
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/full` - IR2 state changes

2. **Distance Events** (non-retained, QoS 0):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/distance/event` - Significant distance changes

3. **Status** (retained, QoS 1):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/status` - Device online/offline

4. **General Events**:
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/event` - Pong responses, config updates

### Subscribed Topics

- `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/cmd` - Remote commands

### Message Format

**Presence Message:**
```json
{
  "site": "garage-01",
  "device": "cabin-A01",
  "sensor": "ir1",
  "present": true,
  "ts": 1234567890.123
}
```

**Distance Message:**
```json
{
  "site": "garage-01",
  "device": "cabin-A01",
  "from_mm": 150,
  "to_mm": 200,
  "ts": 1234567890.123
}
```

## Remote Commands

Send commands to `{DEVICE_ID}/cmd` topic:

- **Ping**: `"ping"` - Device responds with pong
- **Set Publish Interval**: `{"pub_interval": 10}` - Change telemetry interval (seconds)

## Code Modules

### code.py

Main entry point that:
- Connects to Wi-Fi
- Initializes sensors
- Connects to MQTT broker
- Runs main loop:
  - Samples sensors at configured rate
  - Publishes edge events
  - Handles remote commands
  - Reconnects on errors

### config.py

Configuration management:
- Loads settings from `settings.toml`
- Defines MQTT topic structure
- Provides device identity (auto-derived from MAC if not set)

### sensors.py

Sensor hardware interface:
- **Sensors class**: Manages IR sensors and VL53L0X
- **read()**: Reads current sensor values
- **edge_events()**: Detects state changes (edge detection)
- **telemetry()**: Returns current sensor readings

### mqtt_client.py

MQTT client wrapper:
- Handles connection/reconnection
- Publishes JSON messages
- Subscribes to command topic
- Implements Last Will and Testament (LWT)

### net.py

Network management:
- Wi-Fi connection
- Socket pool creation for MQTT

## Operation

### Startup Sequence

1. Load configuration from `settings.toml`
2. Connect to Wi-Fi network
3. Initialize sensors (IR1, IR2, VL53L0X)
4. Connect to MQTT broker
5. Subscribe to command topic
6. Publish online status
7. Enter main loop

### Main Loop

1. **MQTT Loop**: Process incoming messages (1s timeout)
2. **Sensor Sampling**: Read sensors at `SAMPLE_PERIOD` interval (default 0.05s = 20Hz)
3. **Edge Detection**: Compare current vs. previous state
4. **Publish Events**: Send MQTT message on state change
5. **Telemetry**: Periodically publish sensor readings (if enabled)

### Error Handling

- **Wi-Fi Disconnect**: Automatically reconnects
- **MQTT Disconnect**: Automatically reconnects with exponential backoff
- **Sensor Errors**: Logged to serial, loop continues

## Development

### Editing Code

1. Edit files in `cabina_python/` directory
2. Use sync tool to deploy: `python tools/sync_to_esp32.py`
3. CircuitPython auto-reloads on file save
4. Monitor serial output: `python tools/monitor.py`

### Serial Monitor

Monitor device output at 115200 baud:
- Print statements
- Error messages
- MQTT connection status
- Sensor readings

### Debugging

- Use `print()` statements (visible in serial monitor)
- Check MQTT broker logs
- Verify Wi-Fi connectivity
- Test sensors individually

## Troubleshooting

### Wi-Fi Connection Issues

- Verify SSID and password in `settings.toml`
- Check signal strength
- Verify network allows device connections

### MQTT Connection Issues

- Verify broker IP address and port
- Check network connectivity to broker
- Verify MQTT credentials if authentication enabled
- Check broker allows connections

### Sensor Not Working

- Verify pin connections
- Check I2C connections for VL53L0X
- Verify pull-up configuration (`IR_PULLUPS` setting)
- Test sensors individually

### Device Not Appearing as CIRCUITPY

- Reinstall CircuitPython firmware
- Check USB cable (data capable)
- Try different USB port
- Check for driver issues

## Integration with Kiosko

This firmware works with the `kiosko/` Flask application:

1. **Firmware publishes** presence events to MQTT topics
2. **Kiosko subscribes** to the same topics
3. **Kiosko displays** real-time status in web UI

Ensure topic configuration matches between firmware and kiosko:
- Same `TOPIC_BASE`
- Same `SITE_ID`
- Same `DEVICE_ID`

## Performance

- **Sensor Sampling**: 20 Hz (50ms period)
- **MQTT Loop**: 1 second timeout
- **Edge Detection**: Only publishes on state changes
- **Retained Messages**: Presence state retained for new subscribers

## Security Notes

- **Wi-Fi Credentials**: Stored in `settings.toml` (not in git)
- **MQTT Credentials**: Optional, stored in `settings.toml`
- **No Encryption**: MQTT uses plain TCP (consider TLS for production)

## License

See repository root LICENSE file.

