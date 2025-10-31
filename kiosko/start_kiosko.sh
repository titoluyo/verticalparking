#!/usr/bin/env bash
# Simple startup script for Raspberry Pi kiosk mode.
# - Activates venv
# - Starts Flask app and redirects logs to logs/app.log
# Make executable: chmod +x start_kiosko.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
VENV_DIR="$ROOT_DIR/.venv"

mkdir -p "$LOG_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null 2>&1 || true
pip install -r "$ROOT_DIR/requirements.txt" >/dev/null 2>&1

export PORT=${PORT:-5000}

echo "[start_kiosko] Starting app on :$PORT ..." | tee -a "$LOG_DIR/app.log"
python3 "$ROOT_DIR/app.py" >>"$LOG_DIR/app.log" 2>&1 &
echo $! > "$LOG_DIR/app.pid"

# To run at boot with systemd (recommended):
# 1) Create /etc/systemd/system/kiosko.service with:
# [Unit]
# Description=Kiosko POS
# After=network.target
#
# [Service]
# Type=simple
# WorkingDirectory=%h/kiosko-pos
# ExecStart=%h/kiosko-pos/start_kiosko.sh
# Restart=always
# User=pi
#
# [Install]
# WantedBy=multi-user.target
# 2) sudo systemctl daemon-reload && sudo systemctl enable --now kiosko

# Or with cron: (crontab -e)
# @reboot /home/pi/kiosko-pos/start_kiosko.sh

