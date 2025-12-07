# Floor Detection Event Proposal

## Problem Statement

Currently, the kiosko doesn't know when a free cabin reaches the floor level. The system tries to monitor distance from the server side, but this is unreliable because:
1. The server doesn't know the floor level (minimum_distance) for empty cabins
2. Monitoring from server requires constant polling
3. It's more complex and error-prone

## Proposed Solution

Each cabin should detect when it reaches floor level and publish an MQTT event. This is better because:
1. Each cabin knows its own floor level (can be configured via MQTT command)
2. Detection happens locally on the cabin firmware
3. Event-driven architecture - kiosko just listens and reacts
4. More reliable and simpler

## Implementation Plan

### 1. Firmware Changes (cabina_firmware)

#### 1.1 Add Minimum Distance Storage
- Store minimum distance (floor level) in NVS (Non-Volatile Storage)
- Default: uncalibrated (NULL/0 means not calibrated)

#### 1.2 Add MQTT Command to Set Floor Level
- Command topic: `parking/{site}/{device_id}/cmd`
- Command payload: `{"set_floor_level": 450}` (distance in mm)
- Save to NVS for persistence

#### 1.3 Add Floor Detection Logic
- Track minimum distance seen since startup
- Compare current distance with stored floor level
- Detect when: `abs(current_distance - floor_level) <= tolerance` (e.g., 10mm)
- Only trigger event when transitioning TO floor (not already at floor)

#### 1.4 Add Floor Event Publication
- New topic: `parking/{site}/{device_id}/floor/reached`
- Event payload:
  ```json
  {
    "site": "garage-01",
    "device": "cabina-03",
    "distance_mm": 450,
    "floor_level_mm": 450,
    "ts": 1234567890.123
  }
  ```
- Publish only when transitioning TO floor (edge detection)
- QoS: 1, Retain: false

### 2. Kiosko Changes

#### 2.1 Update Motor Control Service
- Remove server-side distance monitoring (let cabins detect floor)
- Keep motor start/stop commands
- Listen for floor/reached events

#### 2.2 Add Floor Event Subscriber
- Subscribe to: `parking/{site}/+/floor/reached` (wildcard for all cabins)
- When event received:
  1. Stop motor
  2. Set that cabin as active
  3. Log the event

#### 2.3 Update Guardar Vehiculo Flow
1. Assign cabin and print ticket
2. Find next free cabin
3. Start motor (if needed)
4. Wait for floor/reached event from that cabin
5. When received: stop motor and activate cabin

## MQTT Topics Structure

### New Topics
- `parking/{site}/{device_id}/floor/reached` - Published when cabin reaches floor
- `parking/{site}/{device_id}/cmd` - Already exists, add new command

### Existing Topics (used)
- `parking/{site}/{device_id}/distance/event` - Distance changes
- `parking/garage-01/motor` - Motor control (ON/OFF)

## Command Examples

### Set Floor Level (from kiosko to cabin)
```bash
# Topic: parking/garage-01/cabina-03/cmd
# Payload: {"set_floor_level": 450}
```

### Floor Reached Event (from cabin to kiosko)
```bash
# Topic: parking/garage-01/cabina-03/floor/reached
# Payload: {"site":"garage-01","device":"cabina-03","distance_mm":450,"floor_level_mm":450,"ts":1234567890.123}
```

## Benefits

1. **Decoupled**: Cabin firmware handles floor detection independently
2. **Reliable**: Each cabin knows its own floor level
3. **Event-driven**: Kiosko just reacts to events
4. **Scalable**: Works the same for all cabins
5. **Simple**: Less complex logic in kiosko

## Migration Path

1. Update firmware to support floor detection
2. Calibrate each cabin (send set_floor_level command)
3. Update kiosko to listen for floor/reached events
4. Test with one cabin first
5. Deploy to all cabins
