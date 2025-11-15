#!/usr/bin/env bash
# Activate the virtual environment and launch the FastAPI server via uvicorn.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

if [ ! -d "$VENV_DIR" ]; then
  echo "Virtualenv missing. Running setup_env.sh ..."
  "$PROJECT_ROOT/setup_env.sh"
fi

source "$VENV_DIR/bin/activate"
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
