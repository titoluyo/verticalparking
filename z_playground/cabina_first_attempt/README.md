# Cabina Firmware - ESP-IDF

ESP-IDF firmware for ESP32-S3 and ESP32-C6 devices that monitors parking sensors and publishes presence data via MQTT. This firmware replaces the CircuitPython implementation in `cabina_python/` with a native C implementation for better performance and lower power consumption.

## Overview

This firmware continuously monitors three sensors:
- **IR1 (Entry Sensor)**: Detects vehicles at the parking entry point
- **IR2 (Full Sensor)**: Detects if the parking space is occupied
- **VL53L0X (Distance Sensor)**: Time-of-flight distance measurement

The firmware uses edge detection to publish MQTT messages only when sensor states change, reducing network traffic and providing real-time event notifications.

## Hardware Requirements

- **ESP32-S3** or **ESP32-C6** development board
- **VL53L0X** time-of-flight distance sensor (I2C)
- **2x IR sensors** (digital inputs)
- ESP-IDF v5.3 or later installed

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

Pins are configurable via `idf.py menuconfig` → Cabina Firmware Configuration.

## Environment Setup

### Windows 11

1. Install Git and Python 3.11 (ensure added to PATH)
2. Install Visual Studio Build Tools (C++ tools, Windows SDK) or MSYS2 (alternative)
3. Install ESP-IDF 5.3 LTS using official installer
   - Launch "ESP-IDF PowerShell Environment" afterwards
   - Verify with `idf.py --version`
4. USB drivers: Install Silicon Labs/CP210x or CH34x as needed for your boards

### Ubuntu 24.04

1. Install system dependencies:
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip cmake ninja-build flex bison gperf ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

2. Clone ESP-IDF:
```bash
git clone -b v5.3 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh all
```

3. Activate environment (run in each new shell):
```bash
. ./esp-idf/export.sh
```

4. Verify installation:
```bash
idf.py --version
```

## Building and Flashing

### Configure Project

1. Set target (choose one):
```bash
idf.py set-target esp32s3
# or
idf.py set-target esp32c6
```

2. Configure settings:
```bash
idf.py menuconfig
```

Navigate to **Cabina Firmware Configuration** and set:
- Wi-Fi SSID and password
- MQTT broker address and port
- MQTT credentials (if required)
- Topic base, site ID, device ID
- Pin mappings (if different from defaults)
- Sampling and publish intervals

### Build

```bash
idf.py build
```

### Flash and Monitor

```bash
idf.py -p COM9 flash monitor
```

Replace `COM9` with your serial port (Windows) or `/dev/ttyUSB0` (Linux).

To exit monitor: `Ctrl+]`

## Configuration

### Kconfig (Compile-time)

Settings configured via `menuconfig` are stored in `sdkconfig` and compiled into the firmware. These serve as defaults.

### NVS (Runtime)

The firmware supports loading configuration from NVS (Non-Volatile Storage) at runtime. If NVS values exist, they override Kconfig defaults. This allows updating settings without recompiling.

**NVS Keys:**
- `wifi_ssid` - Wi-Fi network name
- `wifi_pass` - Wi-Fi password
- `mqtt_broker` - MQTT broker IP address
- `mqtt_port` - MQTT broker port (uint32)
- `mqtt_user` - MQTT username (optional)
- `mqtt_pass` - MQTT password (optional)
- `topic_base` - MQTT topic base (default: "parking")
- `site_id` - Site identifier
- `pub_interval` - Telemetry publish interval in seconds (uint32)
- `sample_period` - Sensor sample period in milliseconds (uint32)
- `dist_threshold` - Distance change threshold in millimeters (uint32, default: 20)
- `presence_retain` - Retain presence messages (uint8: 0/1)
- `ir_pullups` - Enable IR input pull-ups (uint8: 0/1)

**Setting NVS values programmatically:**

You can use ESP-IDF's `nvs_set_*` functions or the `nvs_set` command-line tool. Example using ESP-IDF Python API:

```python
import esptool
# Use esptool or ESP-IDF's nvs_partition_gen.py to create NVS partition
```

For now, configuration is primarily done via `menuconfig`. NVS support is implemented for future runtime configuration updates.

## MQTT Topics

The firmware publishes to these topics (matching `cabina_python` format):

### Published Topics

1. **Presence Events** (retained, QoS 1):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/entry` - IR1 state changes
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/full` - IR2 state changes

2. **Distance Events** (non-retained, QoS 0):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/distance/event` - Significant distance changes

3. **Status** (retained, QoS 1):
   - `{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/status` - Device online/offline (LWT)

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

- **Ping**: `"ping"` - Device responds with pong on event topic
- **Set Publish Interval**: `{"pub_interval": 10}` - Change telemetry interval (seconds)

## Project Structure

```
cabinasensor/esp-idf/cabina_firmware/
├── CMakeLists.txt              # Main build configuration
├── sdkconfig.defaults          # Default Kconfig values
├── partitions.csv              # Flash partition table
├── main/
│   ├── app_main.c              # Main entry point
│   ├── config.h/.c             # Configuration management (Kconfig + NVS)
│   ├── hw_sensors.h/.c         # IR GPIO + I2C init
│   ├── vl53l0x.h/.c            # VL53L0X driver
│   ├── cabina_mqtt.h/.c        # MQTT client wrapper
│   ├── edge_detect.h/.c        # Edge detection state machine
│   ├── telemetry.h/.c          # JSON payload builders
│   └── Kconfig.projbuild       # Menuconfig options
└── README.md                   # This file
```

## Operation

### Startup Sequence

1. Load configuration from NVS (with Kconfig fallback)
2. Connect to Wi-Fi network
3. Initialize sensors (IR1, IR2, VL53L0X)
4. Start SNTP time synchronization
5. Connect to MQTT broker
6. Subscribe to command topic
7. Publish online status
8. Enter main loop

### Main Loop

1. **MQTT Loop**: Process incoming messages (non-blocking)
2. **Sensor Sampling**: Read sensors at configured rate (default 50ms = 20Hz)
3. **Edge Detection**: Compare current vs. previous state
4. **Publish Events**: Send MQTT message on state change
5. **Telemetry**: Periodically publish status heartbeat

### Error Handling

- **Wi-Fi Disconnect**: Automatically reconnects
- **MQTT Disconnect**: Automatically reconnects with exponential backoff
- **Sensor Errors**: Logged to serial, loop continues
- **VL53L0X Errors**: Returns -1 for distance, logged

## Performance

- **Sensor Sampling**: 20 Hz (50ms period, configurable)
- **MQTT Loop**: Non-blocking, processes messages asynchronously
- **Edge Detection**: Only publishes on state changes
- **Retained Messages**: Presence state retained for new subscribers
- **Memory Usage**: ~200KB RAM, ~900KB flash (ESP32-S3)

## Troubleshooting

### Wi-Fi Connection Issues

- Verify SSID and password in `menuconfig` or NVS
- Check signal strength
- Verify network allows device connections
- Check serial logs for connection status

### MQTT Connection Issues

- Verify broker IP address and port
- Check network connectivity to broker (firmware logs diagnostic)
- Verify MQTT credentials if authentication enabled
- Check broker allows connections
- Monitor serial output for connection errors

### Sensor Not Working

- Verify pin connections match configuration
- Check I2C connections for VL53L0X (SDA/SCL)
- Verify pull-up configuration (`IR_PULLUPS` setting)
- Test sensors individually
- Check serial logs for I2C errors

### VL53L0X Distance Sensor

**Accuracy Notes:**
- The VL53L0X sensor has ±2cm accuracy in typical conditions
- Accuracy may decrease at longer ranges (>23cm)
- Status codes 0x5D indicate valid readings with warnings (reduced accuracy)
- Values ending in 0x06/0x07 at longer ranges are normal but may indicate reduced accuracy

**Adjusting Distance Threshold:**
- Default threshold: 20mm (matches CircuitPython implementation)
- Configure via `menuconfig` → Cabina Firmware Configuration → Distance threshold
- Or set NVS key `dist_threshold` (uint32, in millimeters)
- Smaller values = more sensitive (more events)
- Larger values = less sensitive (fewer events)
- Recommended range: 10-50mm depending on use case

**Hardware Testing:**
1. Monitor serial output for sensor readings (logged every 2 seconds)
2. Move object at known distances (e.g., 5cm, 10cm, 20cm, 30cm)
3. Verify distance readings are within ±2cm of actual distance
4. Test distance threshold by moving object slowly and observing when events trigger
5. Adjust threshold if events trigger too frequently or not frequently enough
6. Test at maximum expected range to verify sensor behavior

### Build Issues

- Ensure ESP-IDF environment is activated
- Run `idf.py fullclean` if build cache is corrupted
- Verify target is set: `idf.py set-target esp32s3` or `esp32c6`
- Check `sdkconfig` for configuration errors

## Integration with Kiosko

This firmware works with the `kiosko/` Flask application:

1. **Firmware publishes** presence events to MQTT topics
2. **Kiosko subscribes** to the same topics
3. **Kiosko displays** real-time status in web UI

Ensure topic configuration matches between firmware and kiosko:
- Same `TOPIC_BASE`
- Same `SITE_ID`
- Same `DEVICE_ID`

## Migration from CircuitPython

This ESP-IDF implementation provides feature parity with `cabina_python/`:

- ✅ IR sensor GPIO reading with configurable pull-ups
- ✅ VL53L0X distance sensor via I2C
- ✅ Wi-Fi connectivity
- ✅ MQTT publish/subscribe with LWT
- ✅ Edge detection for state changes
- ✅ JSON message format compatibility
- ✅ Remote command handling
- ✅ SNTP time synchronization
- ✅ NVS configuration storage

**Advantages over CircuitPython:**
- Lower memory footprint
- Better real-time performance
- More efficient power usage
- Native ESP-IDF APIs
- Smaller binary size

## Security Notes

- **Wi-Fi Credentials**: Stored in NVS or compiled into firmware (Kconfig)
- **MQTT Credentials**: Optional, stored in NVS or Kconfig
- **No Encryption**: MQTT uses plain TCP by default (consider TLS for production)
- **NVS Security**: NVS data is stored in flash but not encrypted by default

## License

See repository root LICENSE file.

