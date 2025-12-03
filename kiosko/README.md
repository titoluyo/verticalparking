# Kiosko - Parking Management Web Interface

Flask-based web application for the vertical parking system. Provides a user-friendly interface for managing parking operations and displays real-time sensor data from ESP32 devices via MQTT.

## Overview

The Kiosko application serves as the Point of Sale (POS) and monitoring interface for the parking system. It connects to MQTT brokers to receive real-time presence data from parking sensors and provides a web interface for users to store and retrieve vehicles.

## Features

- **Real-time Sensor Monitoring**: Displays live parking space status from ESP32 sensors via MQTT
- **Vehicle Management**: Interface for storing and retrieving vehicles with ticket printing
- **QR Code Reading**: Camera-based QR code scanning for vehicle retrieval (Raspberry Pi camera support)
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
├── test_camera_qr.py      # Camera QR code reader test script
├── CAMERA_SETUP.md        # Camera setup and testing guide
├── start_kiosko.sh        # Linux/Raspberry Pi startup script
└── start_kiosk.ps1        # Windows PowerShell startup script
```

## Installation

### Prerequisites

- Python 3.10 or higher
- MQTT broker (for sensor data)
- Network access to MQTT broker

### Network Configuration (Raspberry Pi)

#### 1. Set Hostname for mDNS (control.local)

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

#### 2. Configure Static IP Address (DD-WRT Router)

To assign a static IP address to your Raspberry Pi based on its MAC address:

1. **Get your Raspberry Pi's MAC address**:
   ```bash
   bash kiosko/get_mac_address.sh
   ```

2. **Configure static DHCP lease in DD-WRT**:
   - See detailed instructions in [`DD-WRT_STATIC_IP_SETUP.md`](DD-WRT_STATIC_IP_SETUP.md)
   - Typically: **Services** → **DHCP Server** → **Static Leases** → **Add**
   - Enter MAC address and desired IP address (outside DHCP pool range)

**Benefits:**
- Raspberry Pi always gets the same IP address
- Works with both `control.local` (mDNS) and static IP
- Centralized management in router
- Prevents IP conflicts

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
| `KIOSKO_PRINTER_ENABLED` | Enable/disable printer | `true` |
| `KIOSKO_PRINTER_VENDOR_ID` | USB vendor ID (hex, e.g., `0x04f9`) | Auto-detect |
| `KIOSKO_PRINTER_PRODUCT_ID` | USB product ID (hex, e.g., `0x2016`) | Auto-detect |
| `KIOSKO_PRINTER_SERIAL` | Serial port path (e.g., `/dev/ttyUSB0`) | None (use USB) |
| `KIOSKO_PRINTER_BAUDRATE` | Serial baudrate | `9600` |

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
- `GET /guardar` - Store vehicle page (form to confirm vehicle storage)
- `POST /guardar` - Process vehicle storage
  - Creates ticket with unique token
  - Assigns vehicle to available cabin
  - Prints entry ticket with QR code
  - Updates cabin status to 'busy'
  - Sets next free cabin as active
  - Redirects to home page with success/error message
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

- `GET /api/presence/stream` - Server-Sent Events (SSE) stream for real-time presence updates
  - Returns continuous stream of presence status updates
  - Automatically sends keepalive messages every 30 seconds
  - Client should handle reconnection on disconnect

- `GET /api/active-cabin` - Get the current active cabin ID
  Response:
  ```json
  {
    "active_cabin": "cabina-01"
  }
  ```

- `POST /api/active-cabin` - Set the active cabin for vehicle entrance monitoring
  Request body:
  ```json
  {
    "cabin_id": "cabina-02"
  }
  ```
  Response:
  ```json
  {
    "active_cabin": "cabina-02",
    "message": "Active cabin updated"
  }
  ```

- `GET /api/sensors/cabins` - Get sensor status for multiple cabins
  Query parameters:
  - `start` (optional): Start cabin ID, default: `cabina-01`
  - `end` (optional): End cabin ID, default: `cabina-07`
  
  Example: `GET /api/sensors/cabins?start=cabina-01&end=cabina-03`
  
  Response:
  ```json
  {
    "cabins": {
      "cabina-01": {
        "entry": {"present": false, "ts": null},
        "full": {"present": false, "ts": null}
      },
      "cabina-02": {
        "entry": {"present": true, "ts": "2024-01-01T12:00:00Z"},
        "full": {"present": false, "ts": null}
      }
    },
    "timestamp": "2024-01-01T12:00:00Z"
  }
  ```

- `GET /api/printer/status` - Get printer status
  ```json
  {
    "available": true,
    "status": "connected",
    "status_detail": "USB auto-detected",
    "enabled": true
  }
  ```

- `POST /api/printer/test` - Print a test ticket
  ```json
  {
    "success": true,
    "message": "Test ticket printed successfully"
  }
  ```

- `POST /api/printer/entry-ticket` - Print entry ticket
  Request body:
  ```json
  {
    "vehicle_plate": "ABC-123",
    "cabin_id": "cabina-01",
    "timestamp": "2024-01-01 12:00:00",
    "ticket_id": "TKT001"
  }
  ```

- `POST /api/printer/exit-ticket` - Print exit ticket
  Request body:
  ```json
  {
    "vehicle_plate": "ABC-123",
    "entry_time": "2024-01-01 12:00:00",
    "exit_time": "2024-01-01 14:30:00",
    "duration": "2h 30m",
    "cost": "15.50"
  }
  ```

- `POST /api/db/cleanup` - Clean up database (delete tickets and/or reset cabins)
  
  **⚠️ Warning:** This endpoint permanently deletes data. Requires explicit confirmation.
  
  Request body options:
  ```json
  // Clean up everything
  {
    "confirm": true,
    "all": true
  }
  
  // Delete only tickets
  {
    "confirm": true,
    "tickets": true
  }
  
  // Reset only cabins to 'free'
  {
    "confirm": true,
    "cabins": true
  }
  
  // Both tickets and cabins
  {
    "confirm": true,
    "tickets": true,
    "cabins": true
  }
  ```
  
  Response:
  ```json
  {
    "success": true,
    "message": "Cleanup completed successfully",
    "tickets_deleted": 5,
    "cabins_reset": 7
  }
  ```
  
  Example usage:
  ```bash
  # Clean up everything
  curl -X POST http://localhost:5000/api/db/cleanup \
    -H "Content-Type: application/json" \
    -d '{"confirm": true, "all": true}'
  
  # Reset only cabins
  curl -X POST http://localhost:5000/api/db/cleanup \
    -H "Content-Type: application/json" \
    -d '{"confirm": true, "cabins": true}'
  ```

### Usage Examples

#### Storing a Vehicle

1. **Via Web UI:**
   - Navigate to `/guardar` when vehicle is detected (state = "entered")
   - Click "Confirmar y Guardar" button
   - System will:
     - Find available cabin
     - Generate unique token
     - Save ticket to database
     - Print entry ticket with QR code
     - Update cabin status to 'busy'
     - Set next free cabin as active

2. **Via API (for testing):**
   ```bash
   # Get active cabin
   curl http://localhost:5000/api/active-cabin
   
   # Store vehicle (triggers print automatically)
   curl -X POST http://localhost:5000/guardar
   ```

#### Database Management

**View current state:**
```bash
# Check all cabins status (via database query)
sqlite3 kiosko.db "SELECT * FROM cabinas;"

# Check active tickets
sqlite3 kiosko.db "SELECT * FROM tickets WHERE status='active';"
```

**Reset database:**
```bash
# Clean everything and start fresh
curl -X POST http://localhost:5000/api/db/cleanup \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "all": true}'
```

### Swagger Documentation

Interactive API documentation is available at:
```
http://localhost:5000/apidocs/
```

## Database

The application uses SQLite database (`kiosko.db`) with the following schema:

### Tables

**registros** (legacy table):
```sql
CREATE TABLE registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    placa TEXT NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**tickets** (parking tickets):
```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    cabina_id TEXT NOT NULL,
    entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    exit_timestamp DATETIME,
    vehicle_plate TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled'))
)
```

**cabinas** (cabin status):
```sql
CREATE TABLE cabinas (
    id TEXT PRIMARY KEY,
    estado TEXT NOT NULL DEFAULT 'free' CHECK(estado IN ('free', 'busy')),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

### Database Management

The database is automatically initialized on first run with:
- All tables created
- Cabins 01-07 initialized with status 'free'
- Indexes created for performance

**Cleanup operations:**
- Use `/api/db/cleanup` endpoint to reset data
- See [Usage Examples > Database Management](#usage-examples) section for examples

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

### Thermal Printer (Cashino KP-300)

The `printer.py` module provides thermal printer support for printing parking tickets:
- Supports USB and serial (RS232) connections
- Automatic USB device detection
- Graceful fallback to simulation mode when printer unavailable
- Thread-safe printing operations

#### Printer Setup (Complete Guide)

**For Cashino KP-300 with ICS Advent Parallel Adapter (USB ID: 0fe6:811e)**

**Quick Setup (Automated):**
```bash
cd ~/verticalparking/kiosko
bash setup_printer.sh
```
Then **log out and log back in** for group membership to take effect.

**Manual Setup:**

1. **Install system dependencies:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y libusb-1.0-0-dev
   ```

2. **Install Python dependencies:**
   ```bash
   cd ~/verticalparking/kiosko
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   
   This installs `python-escpos` and `pyusb` automatically.

3. **Connect printer:**
   - Connect Cashino KP-300 via USB cable to Raspberry Pi
   - Power on the printer and load 80mm thermal paper
   - Verify connection: `lsusb` should show "ICS Advent Parallel Adapter" (ID 0fe6:811e)

4. **Set up USB permissions (REQUIRED):**
   ```bash
   # Create udev rule for the printer
   sudo nano /etc/udev/rules.d/99-escpos-printer.rules
   ```
   
   Add this line to the file:
   ```
   SUBSYSTEM=="usb", ATTRS{idVendor}=="0fe6", ATTRS{idProduct}=="811e", MODE="0666", GROUP="dialout"
   ```
   
   Save and exit (Ctrl+X, then Y, then Enter).
   
   Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

5. **Add user to dialout group:**
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   
   **Important:** Log out and log back in (or reboot) for group membership to take effect.
   
   To test immediately without logging out:
   ```bash
   newgrp dialout
   ```

6. **Test printer:**
   ```bash
   # Test directly with Python (with proper cleanup)
   cd ~/verticalparking/kiosko
   source .venv/bin/activate
   python3 -c "from escpos.printer import Usb; p = Usb(0x0fe6, 0x811e); p.text('Test\n'); p.cut(); p.close()"
   ```
   
   Or use a test script with error handling:
   ```bash
   python3 << 'EOF'
   from escpos.printer import Usb
   try:
       p = Usb(0x0fe6, 0x811e)
       p.text('Test\n')
       p.cut()
       print('Print successful!')
   except Exception as e:
       print(f'Error: {e}')
   finally:
       try:
           p.close()
       except:
           pass
   EOF
   ```
   
   Or test via API (after starting Flask app):
   ```bash
   curl -X POST http://localhost:5000/api/printer/test
   ```

**For other printers:**

- **Find USB device IDs:**
  ```bash
  lsusb
  # Look for your printer, note vendor and product IDs
  # Example: Bus 001 Device 005: ID 04f9:2016 Brother Industries, Ltd
  # Vendor ID: 0x04f9, Product ID: 0x2016
  ```

- **Configure printer (optional):**
  ```bash
  # Set USB vendor/product IDs if auto-detection fails
  export KIOSKO_PRINTER_VENDOR_ID=0x04f9
  export KIOSKO_PRINTER_PRODUCT_ID=0x2016
  
  # Or use serial connection
  export KIOSKO_PRINTER_SERIAL=/dev/ttyUSB0
  export KIOSKO_PRINTER_BAUDRATE=9600
  
  # Disable printer if needed
  export KIOSKO_PRINTER_ENABLED=false
  ```

- **Update udev rule** with your printer's vendor/product IDs if different from Cashino KP-300.

#### Printer Troubleshooting

- **Printer not detected:**
  - Check USB connection: `lsusb` should show the printer
  - Verify python-escpos is installed: `pip list | grep escpos`
  - Verify pyusb is installed: `pip list | grep pyusb`
  - Try specifying vendor/product IDs manually via environment variables
  - Check application logs for printer initialization errors

- **"USB library required" error:**
  - Install system library: `sudo apt-get install libusb-1.0-0-dev`
  - Install Python library: `pip install pyusb`
  - Restart the application after installing dependencies

- **"Access denied (insufficient permissions)" error:**
  - Create udev rule: `sudo nano /etc/udev/rules.d/99-escpos-printer.rules`
  - Add: `SUBSYSTEM=="usb", ATTRS{idVendor}=="0fe6", ATTRS{idProduct}=="811e", MODE="0666", GROUP="dialout"`
  - Reload: `sudo udevadm control --reload-rules && sudo udevadm trigger`
  - Add user to dialout group: `sudo usermod -a -G dialout $USER`
  - **Log out and log back in** for group membership to take effect

- **Permission errors (Linux):**
  ```bash
  # Add user to dialout group for serial access
  sudo usermod -a -G dialout $USER
  # Log out and back in for changes to take effect
  ```

- **Printer in simulation mode:**
  - This is normal if printer is not connected or unavailable
  - Check printer status: `GET /api/printer/status`
  - Simulation mode logs ticket content instead of printing

- **Print quality issues:**
  - Ensure 80mm thermal paper is loaded correctly
  - Check paper roll diameter (max 150mm)
  - Verify paper thickness (55-200μm)
  - Clean print head if needed

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

### Camera Testing

Test the Raspberry Pi camera for QR code reading:
```bash
# Install dependencies first (see CAMERA_SETUP.md)
python test_camera_qr.py
```

See [`CAMERA_SETUP.md`](CAMERA_SETUP.md) for detailed camera setup instructions.

### Logging

Logs are written to:
- Console (development)
- `logs/app.log` (production via startup script)

## Dependencies

- **Flask** (>=2.2): Web framework
- **flasgger** (>=0.9.7.1): Swagger/OpenAPI documentation
- **paho-mqtt** (>=1.6): MQTT client library
- **python-escpos** (>=3.0.0): Thermal printer support (ESC/POS protocol)
- **pyusb** (>=1.2.0): USB device access for thermal printers (required for USB connection)
- **opencv-python** (>=4.8.0): Camera and image processing for QR code reading
- **pyzbar** (>=0.1.9): QR code and barcode detection
- **picamera2** (>=0.3.12): Raspberry Pi camera interface (Linux only)

## Related Components

- **cabina_python/**: ESP32-S3 sensor firmware that publishes MQTT messages
- **api/**: FastAPI backend service (separate component)

## License

See repository root LICENSE file.

