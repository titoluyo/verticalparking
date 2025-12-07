# Cabina Floor Event Implementation Guide

## Overview

This document describes how to implement the floor detection event system where each cabin firmware detects when it reaches floor level and publishes an MQTT event. The kiosko then listens to these events and reacts accordingly.

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Cabina    │         │ MQTT Broker  │         │   Kiosko    │
│  Firmware   │────────>│              │<────────│             │
│             │         │              │         │             │
│ Detects     │         │  Topics:     │         │ Listens &   │
│ floor level │         │  - floor/    │         │ reacts      │
│ Publishes   │         │    reached   │         │ - Stop motor│
│ event       │         │              │         │ - Activate  │
└─────────────┘         └──────────────┘         └─────────────┘
```

## MQTT Event Specification

### Topic
```
parking/{site}/{device_id}/floor/reached
```

Example: `parking/garage-01/cabina-03/floor/reached`

### Message Format (JSON)
```json
{
  "site": "garage-01",
  "device": "cabina-03",
  "distance_mm": 450,
  "floor_level_mm": 450,
  "ts": 1234567890.123
}
```

### QoS and Retain
- QoS: 1 (at least once delivery)
- Retain: false (don't retain, just notify)

## Firmware Changes Required

### 1. Store Floor Level in NVS

Add to `cabina_config_t` or store separately in NVS:
- Floor level (minimum distance) in mm
- Default: 0 (uncalibrated)

### 2. Add MQTT Command to Set Floor Level

Extend `handle_cmd()` in `app_main.c`:
```c
// Command: {"set_floor_level": 450}
int floor_level = 0;
if (sscanf(msg, "{\"set_floor_level\": %d}", &floor_level) == 1 && floor_level > 0) {
    // Save to NVS
    // Update stored floor level
}
```

### 3. Add Floor Detection Logic

Track when cabin reaches floor:
- Store floor level from NVS on startup
- Compare current distance with floor level
- Detect: `abs(current_distance - floor_level) <= tolerance` (e.g., 10mm)
- Only trigger event when transitioning TO floor (edge detection)

### 4. Add Floor Event Publication

New function in `telemetry.c`:
```c
char *json_floor_reached(const cabina_config_t *cfg, int distance_mm, int floor_level_mm) {
    // Returns JSON for floor/reached event
}
```

Publish event in main loop when floor detected.

## Kiosko Changes (Already Implemented)

The kiosko code is being updated to:
1. Subscribe to `parking/{site}/{device_id}/floor/reached` topics
2. Process floor/reached events
3. Stop motor when event received
4. Activate the cabin that reached floor

## Workflow

1. **User saves vehicle** → Cabin assigned, ticket printed
2. **Kiosko finds next free cabin** (circular order)
3. **Kiosko starts motor** → Sends "ON" to `parking/garage-01/motor`
4. **Cabin moves down** → Distance decreases
5. **Cabin detects floor** → `abs(current_distance - floor_level) <= 10mm`
6. **Cabin publishes event** → `parking/garage-01/cabina-03/floor/reached`
7. **Kiosko receives event** → Stops motor, activates cabin
8. **Ready for next vehicle** → Cabin is at floor and active
