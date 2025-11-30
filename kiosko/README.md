# Kiosko - Parking Management Web Interface

Flask-based web application for the vertical parking system. Provides a user-friendly interface for managing parking operations and displays real-time sensor data from ESP32 devices via MQTT.

## Overview

The Kiosko application serves as the Point of Sale (POS) and monitoring interface for the parking system. It connects to MQTT brokers to receive real-time presence data from parking sensors and provides a web interface for users to store and retrieve vehicles.

## Features

- **Real-time Sensor Monitoring**: Displays live parking space status from ESP32 sensors via MQTT
- **Vehicle Management**: Interface for storing and retrieving vehicles (UI ready, database integration pending)
- **REST API**: JSON API endpoints for frontend integration
- **Swagger Documentation**: Interactive API documentation at `/apidocs/`
- **Cross-platform**: Runs on Windows 11 and Raspberry Pi OS
- **MQTT Integration**: Subscribes to sensor presence topics for real-time updates

## Project Structure

```
kiosko/
├── app/                    # Flask application package
│   ├── __init__.py        # Application factory and setup
│   ├── routes.py          # Web UI route handlers
│   ├── api.py             # REST API endpoints
│   ├── database.py        # SQLite database operations
│   ├── presence.py        # MQTT presence service
│   └── hardware.py        # Raspberry Pi GPIO integration
├── static/                # Static assets
│   ├── css/
│   │   └── style.css      # Stylesheet
│   └── js/
│       └── main.js        # Frontend JavaScript (presence polling)
├── templates/             # Jinja2 templates
│   ├── base.html          # Base template
│   ├── index.html         # Landing page with presence indicator
│   ├── guardar.html       # Store vehicle page
│   ├── recoger.html       # Retrieve vehicle page
│   ├── login.html         # Login page (placeholder)
│   └── register.html      # Registration page (placeholder)
├── logs/                  # Application logs
│   └── app.log
├── app.py                 # Main entry point
├── requirements.txt       # Python dependencies
├── start_kiosko.sh        # Linux/Raspberry Pi startup script
└── start_kiosk.ps1        # Windows PowerShell startup script
```

## Installation

### Prerequisites

- Python 3.10 or higher
- MQTT broker (for sensor data)
- Network access to MQTT broker

### Network Configuration (Raspberry Pi)

To configure your Raspberry Pi to be accessible as `control.local` on your network:

1. **Run the hostname setup script** (requires sudo):
   ```bash
   sudo bash kiosko/setup_hostname.sh
   ```

   This script will:
   - Set the hostname to `control`
   - Install and configure Avahi (mDNS daemon) if needed
   - Enable `.local` hostname resolution

2. **Verify the setup**:
   ```bash
   # On the Raspberry Pi
   hostname  # Should show "control"
   
   # From another device on the network
   ping control.local
   ```

3. **Access your Raspberry Pi**:
   - Via hostname: `http://control.local:5000`
   - Via IP address: `http://<raspberry-pi-ip>:5000`

**Note:** The `.local` hostname uses mDNS (multicast DNS) and works automatically on most modern operating systems (Windows 10+, macOS, Linux). It may take a few seconds after boot for the hostname to be available on the network.

### Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   ```

2. **Activate virtual environment:**
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

The application can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP server port | `5000` |
| `SECRET_KEY` | Flask session secret key | `"change-this-in-production"` |
| `KIOSKO_MQTT_HOST` | MQTT broker hostname/IP | `127.0.0.1` |
| `KIOSKO_MQTT_PORT` | MQTT broker port | `1883` |
| `KIOSKO_MQTT_USER` | MQTT username (optional) | `None` |
| `KIOSKO_MQTT_PASSWORD` | MQTT password (optional) | `None` |
| `KIOSKO_TOPIC_BASE` | MQTT topic root namespace | `"parking"` |
| `KIOSKO_SITE_ID` | Site identifier | `"default-site"` |
| `KIOSKO_DEVICE_ID` | Device identifier | `"esp32-sensor"` |
| `KIOSKO_TOPIC_ENTRY` | Entry sensor topic (override) | Auto-generated |
| `KIOSKO_TOPIC_FULL` | Full sensor topic (override) | Auto-generated |

**Fallback variables:** The app also checks `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`, `TOPIC_BASE`, `SITE_ID`, and `DEVICE_ID` if the `KIOSKO_*` variants are not set.

### MQTT Topic Structure

The application subscribes to MQTT topics following this pattern:
```
{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/entry
{TOPIC_BASE}/{SITE_ID}/{DEVICE_ID}/presence/full
```

Example: `parking/garage-01/cabin-A01/presence/entry`

## Usage

### Development Mode

Run the Flask development server:

```bash
# Activate venv first
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Run the app
python app.py
```

The application will be available at `http://localhost:5000`

### Production Mode (Raspberry Pi)

Use the startup script:

```bash
bash start_kiosko.sh
```

This script:
- Creates/activates virtual environment
- Installs dependencies if needed
- Starts the Flask app
- Logs output to `logs/app.log`

### Windows PowerShell

```powershell
.\start_kiosk.ps1
```

## API Endpoints

### Web Routes

- `GET /` - Landing page with presence indicator and main actions
- `GET /guardar` - Store vehicle page
- `GET /recoger` - Retrieve vehicle page

### REST API

- `GET /api/presence` - Get current sensor presence status
  ```json
  {
    "entry": {
      "present": true,
      "ts": "2024-01-01T12:00:00Z"
    },
    "full": {
      "present": false,
      "ts": "2024-01-01T12:00:00Z"
    },
    "occupied": false,
    "status": "online",
    "status_detail": null,
    "connected": true,
    "updated_at": "2024-01-01T12:00:00Z"
  }
  ```

### Swagger Documentation

Interactive API documentation is available at:
```
http://localhost:5000/apidocs/
```

## Database

The application uses SQLite database (`kiosko.db`) with the following schema:

```sql
CREATE TABLE registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    placa TEXT NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

The database is automatically initialized on first run.

## MQTT Integration

### Presence Service

The `PresenceService` class (`app/presence.py`) runs as a background thread and:

1. Connects to MQTT broker
2. Subscribes to presence topics
3. Maintains in-memory state of sensor readings
4. Provides thread-safe snapshot API

### Message Format

Expected MQTT message format:
```json
{
  "site": "garage-01",
  "device": "cabin-A01",
  "sensor": "ir1",
  "present": true,
  "ts": 1234567890.123
}
```

**Sensor Names:**
- `ir1` (Entry Sensor): Detects when a vehicle starts entering the cabin
- `ir2` (Full Sensor): Detects when a vehicle is fully entered into the cabin

## Frontend

The frontend uses vanilla JavaScript to:
- Poll `/api/presence` every 3 seconds
- Update UI indicators based on sensor status
- Display connection status and last update time

### Presence States

- **Occupied** (red): Vehicle fully entered in cabin (IR2 sensor active)
- **Free** (green): Space available (no vehicle detected)
- **Idle** (gray): No data received yet
- **Error** (yellow): Connection issues

The system uses two IR sensors:
- **Entry Sensor (IR1)**: Located at the beginning of the cabin, detects when a vehicle starts entering
- **Full Sensor (IR2)**: Located at the end of the cabin, detects when a vehicle is fully entered

## Hardware Integration

### Raspberry Pi GPIO

The `hardware.py` module provides optional GPIO control:
- Controls LED on GPIO 17 (2 seconds on)
- Falls back to simulation on non-Linux platforms

## Troubleshooting

### MQTT Connection Issues

- Verify MQTT broker is running and accessible
- Check network connectivity
- Verify topic names match between sensor and kiosko
- Check MQTT credentials if authentication is enabled

### Presence Service Not Starting

- Check application logs in `logs/app.log`
- Verify MQTT broker configuration
- Application will continue running even if MQTT fails (graceful degradation)

### Database Issues

- Database is auto-created on first run
- Check file permissions in `kiosko/` directory
- Database file: `kiosko.db`

## Development

### Code Structure

- **Application Factory Pattern**: Uses Flask's app factory for better testability
- **Blueprints**: Routes organized into blueprints (`routes`, `api`)
- **Background Services**: MQTT service runs in separate thread
- **Type Hints**: Python type hints used throughout

### Testing

Run tests (when available):
```bash
pytest
```

### Logging

Logs are written to:
- Console (development)
- `logs/app.log` (production via startup script)

## Dependencies

- **Flask** (>=2.2): Web framework
- **flasgger** (>=0.9.7.1): Swagger/OpenAPI documentation
- **paho-mqtt** (>=1.6): MQTT client library

## Related Components

- **cabina_python/**: ESP32-S3 sensor firmware that publishes MQTT messages
- **api/**: FastAPI backend service (separate component)

## License

See repository root LICENSE file.

