#!/bin/bash
# Setup script for Linux/Ubuntu - Creates venv and installs dependencies

set -e  # Exit on error

echo "========================================"
echo "ESP32-S3 Development Tools Setup"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR"
VENV_DIR="$TOOLS_DIR/.venv"

echo "[1/3] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install it with: sudo apt update && sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
python3 --version
echo ""

echo "[2/3] Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at: $VENV_DIR"
    echo "Skipping creation..."
else
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully!"
fi
echo ""

echo "[3/3] Installing dependencies..."
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

python -m pip install --upgrade pip --quiet
pip install -r "$TOOLS_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi
echo ""

echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "To use the tools, activate the virtual environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Then run:"
echo "  python sync_to_esp32.py"
echo "  python monitor.py"
echo ""
echo "Or make scripts executable and run directly:"
echo "  chmod +x sync.sh monitor.sh"
echo "  ./sync.sh"
echo "  ./monitor.sh"
echo ""

# Make shell scripts executable
chmod +x "$TOOLS_DIR/sync.sh" "$TOOLS_DIR/monitor.sh" 2>/dev/null || true
echo "Shell scripts made executable."
echo ""

