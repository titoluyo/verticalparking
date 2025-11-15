# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a vertical parking system with three main components:
- **kiosko**: Flask-based web UI for parking management and monitoring
- **cabinasensor**: Embedded sensor firmware for ESP32 devices using CircuitPython/Arduino
- **diseno3d**: CAD files and 3D models for the physical parking structure

## Development Commands

### Kiosko (Flask Web App)
- Setup: `python3 -m venv kiosko/.venv && source kiosko/.venv/bin/activate && pip install -r kiosko/requirements.txt`
- Development: `python kiosko/app.py` (runs on port 5000, configurable via PORT env var)
- Production startup: `bash kiosko/start_kiosko.sh` (creates logs in `kiosko/logs/`)
- Access Swagger docs at `/apidocs/` when running

### Sensor Firmware (CircuitPython)
- Main sensor code is in `cabinasensor/cabina_python/`
- Entry point: `cabinasensor/cabina_python/code.py`
- Configuration: Edit `cabinasensor/cabina_python/config.py` for MQTT and device settings
- Deploy by copying files to CircuitPython device

## Architecture

### Flask Application Structure
- **kiosko/app.py**: Main entry point, creates Flask app factory
- **kiosko/app/__init__.py**: Application factory with DB initialization, Swagger setup, and MQTT presence service
- **kiosko/app/routes.py**: Web UI route handlers
- **kiosko/app/api.py**: REST API endpoints
- **kiosko/app/database.py**: SQLite database operations
- **kiosko/app/presence.py**: MQTT client for real-time sensor data
- **kiosko/app/hardware.py**: Hardware interface abstractions

### Sensor Architecture
- **CircuitPython-based** sensors on ESP32 devices
- **MQTT communication** for real-time data transmission
- **Edge event detection** with configurable thresholds
- Modular design: sensors, networking, and MQTT client are separate modules

### Communication Flow
1. Sensors detect vehicle presence/absence and publish events via MQTT
2. Flask app subscribes to MQTT topics and caches presence data
3. Web UI displays real-time status via REST API endpoints
4. System supports remote configuration of sensor parameters via MQTT commands

## Key Configuration
- Flask app uses SQLite database (auto-initialized)
- MQTT broker configuration in sensor `config.py` files
- Environment variables: `PORT` for Flask, `SECRET_KEY` for sessions
- Sensor thresholds and intervals configurable via MQTT commands

## Testing and Validation
- Sensor testing via serial monitor and MQTT message inspection
- Flask app testing through web interface and API endpoints
- Logs available in `kiosko/logs/` for production debugging