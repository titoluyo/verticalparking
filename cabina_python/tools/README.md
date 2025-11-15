# ESP32-S3 Development Tools

Development tools for working with the `cabina_python` CircuitPython firmware. These tools help sync code to the ESP32-S3 device and monitor serial output during development.

**Note:** This is a subfolder of `cabina_python/`. See the parent directory README for firmware documentation.

## Setup

### Windows

Run the setup script to create a virtual environment and install dependencies:

**PowerShell (recommended):**
```powershell
cd cabina_python\tools
.\setup.ps1
```

**Command Prompt:**
```cmd
cd cabina_python\tools
setup.bat
```

**Note:** If you get an execution policy error in PowerShell, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux/Ubuntu

Run the setup script (make it executable first):

```bash
cd cabina_python/tools
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a Python virtual environment (`.venv/`)
- Install required packages (`pyserial`)
- Set up everything needed to run the tools

**Note:** If you prefer to install packages globally, you can skip setup and just run:
```bash
pip install pyserial
```

## Usage

### Sync Code to ESP32-S3

Sync all Python files and settings from `cabina_python/` to the CIRCUITPY drive:

**Windows PowerShell:**
```powershell
cd cabina_python\tools
.\sync.ps1
```

**Windows Command Prompt:**
```cmd
cd cabina_python\tools
sync.bat
```

**Linux/Ubuntu:**
```bash
cd cabina_python/tools
./sync.sh
```

**Or use Python directly (after activating venv):**
```bash
# Activate venv first (if using setup)
source .venv/bin/activate  # Linux
.venv\Scripts\activate.bat  # Windows

# Then run
python sync_to_esp32.py
```

The script will:
- Automatically find the CIRCUITPY drive
- Copy all necessary files (`code.py`, `config.py`, `sensors.py`, `mqtt_client.py`, `net.py`, `settings.toml`)
- Show which files were synced successfully

**Note:** CircuitPython will automatically reload when files are saved to the CIRCUITPY drive.

### Monitor Serial Output

Monitor real-time output from the ESP32-S3:

**Windows PowerShell:**
```powershell
cd cabina_python\tools
.\monitor.ps1
```

**Windows Command Prompt:**
```cmd
cd cabina_python\tools
monitor.bat
```

**Linux/Ubuntu:**
```bash
cd cabina_python/tools
./monitor.sh
```

**Or use Python directly (after activating venv):**
```bash
python monitor.py
```

The monitor will:
- Automatically detect the ESP32-S3 serial port
- Display all serial output at 115200 baud
- Show print statements, errors, and MQTT connection status

Press `Ctrl+C` to stop monitoring.

## Development Workflow

1. **Edit code in Cursor** - Make changes to files in `cabina_python/`
2. **Sync to device** - Run `python tools/sync_to_esp32.py`
3. **Monitor output** - Run `python tools/monitor.py` in a separate terminal
4. **Test changes** - Watch serial output for errors or MQTT messages
5. **Iterate** - Repeat steps 1-4

## Troubleshooting

### CIRCUITPY drive not found
- Make sure ESP32-S3 is connected via USB
- Verify CircuitPython firmware is installed
- Check that the device appears as a drive in File Explorer

### Serial port not found
- Install USB-to-Serial drivers (CH340 or CP2102)
- Check Device Manager (Windows) for COM port
- Make sure no other program is using the serial port
- Try unplugging and reconnecting the USB cable

### Files not syncing
- Check that CIRCUITPY drive is not read-only
- Verify you have write permissions
- Make sure the device is not in bootloader mode

## Files Synced

The sync script copies these files:
- `code.py` - Main entry point
- `config.py` - Configuration settings
- `sensors.py` - Sensor hardware interface
- `mqtt_client.py` - MQTT client implementation
- `net.py` - Network/Wi-Fi setup
- `settings.toml` - Wi-Fi and MQTT credentials

**Note:** The `lib/` folder is not synced automatically. Copy libraries manually if needed.

