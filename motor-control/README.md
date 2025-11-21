# Motor Control (ESP32-S3)

ESP-IDF app for an ESP32-S3 Super Mini that listens on the MQTT topic
`parking/garage-01/motor` and toggles a 3.3 V relay to drive a motor. The relay
is controlled through a configurable GPIO (default `GPIO10`) and accepts `ON`
or `OFF` MQTT payloads.

## Prerequisites

- ESP-IDF 5.5 environment (activate with `startespidfenv.ps1` in repo root or
  run `\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-29323a3f5a0574597d6dbaa0af20c775`).
- ESP32-S3 Super Mini board connected over USB (identify the COM port).

## Configure

```powershell
cd C:\work\verticalparking
.\startespidfenv.ps1
cd motor-control
idf.py set-target esp32s3
idf.py menuconfig
```

In **Motor Control Configuration** set:

- `Relay GPIO number` / `Relay turns on with logic HIGH`
- `Wi-Fi SSID` and `Wi-Fi password`
- `MQTT broker URI`, credentials, client ID, and topic (defaults already set)

## Build & Flash

```powershell
idf.py build
idf.py -p COM7 flash monitor     # replace COM7 with your serial port
```

On boot the firmware connects to Wi-Fi, subscribes to
`parking/garage-01/motor`, and toggles the relay whenever it receives `ON` or
`OFF` (case-insensitive). The relay defaults to `OFF` if no commands are
received.

## MQTT Control

- Topic: `parking/garage-01/motor`
- Payloads: `ON` to energize the relay, `OFF` to de-energize
- QoS: Configurable (default `1`)

The log output in `idf.py monitor` reports relay state transitions, Wi-Fi
events, and MQTT connection status to aid troubleshooting.

