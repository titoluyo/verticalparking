# Multi-Device Management Guide

This guide explains how to manage multiple ESP32 cabins with different device IDs.

## Overview

Each cabin needs a unique `CONFIG_EXAMPLE_MQTT_DEVICE_ID` (e.g., `cabina-00`, `cabina-01`, etc.) to:
- Subscribe to device-specific MQTT topics
- Publish telemetry with correct device identification
- Receive targeted OTA update commands

## Initial Flashing

### Option 1: Flash Individual Device

Use `flash_cabin.py` to flash a single device with a specific device ID:

```powershell
# In ESP-IDF environment
python flash_cabin.py --device-id cabina-01 --port COM3
python flash_cabin.py --device-id cabina-02 --port COM4 --monitor
```

**What it does:**
1. Updates `sdkconfig` with the specified device ID
2. Builds the firmware
3. Flashes to the specified port
4. Optionally starts serial monitor

### Option 2: Batch Flash Multiple Devices

Edit `flash_all_cabins.py` and update the `CABINS` list:

```python
CABINS = [
    ["cabina-01", "COM3"],
    ["cabina-02", "COM4"],
    ["cabina-03", "COM5"],
    # Add more as needed
]
```

Then run:
```powershell
python flash_all_cabins.py
```

## OTA Updates

### Single Device OTA

Send OTA command via MQTT:

```powershell
mosquitto_pub -h 192.168.10.50 -t "parking/garage-01/cabina-01/ota/update" -m '{"url":"http://192.168.10.147:8080/cabina-firmware.bin"}'
```

### Multiple Devices OTA (Same Firmware)

Use `ota_update_all.py` to update multiple devices with the same firmware:

```powershell
# Update all default devices
python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin

# Update specific devices
python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --device-id cabina-01 --device-id cabina-02

# Update devices in different site
python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --site-id garage-02
```

### Multiple Devices OTA (Different Firmware per Device)

If you need to send different firmware binaries to different devices:

**Option 1: Use URL mapping file**

1. Create a JSON file mapping device IDs to firmware URLs:
```json
{
  "cabina-01": "http://192.168.10.147:8080/cabina-firmware-cabina-01.bin",
  "cabina-02": "http://192.168.10.147:8080/cabina-firmware-cabina-02.bin",
  "cabina-03": "http://192.168.10.147:8080/cabina-firmware-cabina-03.bin"
}
```

2. Run OTA update with URL map:
```powershell
python ota_update_all.py --url-map url_map.json
```

**Option 2: Build device-specific firmware binaries**

1. Build separate firmware binaries for each device:
```powershell
# Build for specific devices
python build_multi_firmware.py --device-ids cabina-01 cabina-02 cabina-03

# Build for all default devices
python build_multi_firmware.py --all
```

This creates firmware binaries in `firmware_builds/` directory:
- `cabina-firmware-cabina-01.bin`
- `cabina-firmware-cabina-02.bin`
- etc.

2. Serve the firmware files (e.g., copy to HTTP server directory)

3. Use URL mapping file to send correct firmware to each device

**Note:** The OTA script requires `paho-mqtt` Python package:
```powershell
pip install paho-mqtt
```

## Device Configuration

### MQTT Topics Structure

Each device uses the following topic pattern:
```
{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/{SUBTopic}
```

Example for `cabina-01` in `garage-01`:
- Commands: `parking/garage-01/cabina-01/cmd`
- Status: `parking/garage-01/cabina-01/status`
- OTA Update: `parking/garage-01/cabina-01/ota/update`
- OTA Status: `parking/garage-01/cabina-01/ota/status`
- OTA Version: `parking/garage-01/cabina-01/ota/version`

### Configuration Files

- **`sdkconfig`**: Contains device-specific config (device ID, WiFi, MQTT)
- **`sdkconfig.defaults`**: Contains shared defaults (partition table, OTA settings)
- **`flash_cabin.py`**: Script to update device ID and flash

## Best Practices

### 1. Keep a Device Inventory

Create a file `devices.csv` or similar:
```csv
device_id,port,location,notes
cabina-01,COM3,Floor 1 - Bay A,Initial deployment
cabina-02,COM4,Floor 1 - Bay B,Initial deployment
cabina-03,COM5,Floor 2 - Bay A,Added 2025-01-15
```

### 2. Use Consistent Naming

- Device IDs: `cabina-01`, `cabina-02`, etc. (zero-padded for sorting)
- Site IDs: `garage-01`, `garage-02`, etc.
- Keep naming consistent across all devices

### 3. Test OTA on One Device First

Before updating all devices:
1. Test OTA on a single device (`cabina-01`)
2. Verify it works correctly
3. Then update all devices

### 4. Monitor OTA Progress

Subscribe to OTA status topics:
```powershell
mosquitto_sub -h 192.168.10.50 -t "parking/garage-01/+/ota/status" -v
```

### 5. Version Management

- Use Git tags for versioning: `git tag v1.0.1`
- The version appears in logs and MQTT messages
- Check version after OTA to confirm update

## Troubleshooting

### Device Not Responding to OTA

1. Check MQTT connection: `mosquitto_sub -h 192.168.10.50 -t "parking/garage-01/cabina-01/status" -v`
2. Verify device ID matches: Check serial logs on boot
3. Check OTA status topic for error messages

### Wrong Device ID After Flash

1. Verify `sdkconfig` was updated: `grep CONFIG_EXAMPLE_MQTT_DEVICE_ID sdkconfig`
2. Rebuild after changing device ID: `idf.py build`
3. Flash again with correct device ID

### OTA Update Fails

1. Check HTTP server is accessible: `curl http://192.168.10.147:8080/cabina-firmware.bin -I`
2. Verify firmware binary exists and is correct size
3. Check device logs for specific error messages
4. Ensure `CONFIG_ESP_HTTPS_OTA_ALLOW_HTTP=y` is set

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `flash_cabin.py` | Flash single device with specific device ID |
| `flash_all_cabins.py` | Batch flash multiple devices |
| `ota_update_all.py` | Send OTA updates to multiple devices via MQTT |
| `start_ota_server.ps1` | Start HTTP server for OTA firmware distribution |

