#!/bin/bash
# Quick monitor script for Linux
# Uses venv if available, otherwise uses system Python

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ -f "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" "$SCRIPT_DIR/monitor.py"
else
    python3 "$SCRIPT_DIR/monitor.py"
fi

