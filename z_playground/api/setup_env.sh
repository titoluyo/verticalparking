#!/usr/bin/env bash
# Bootstrap a local virtual environment and install dependencies.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_ROOT/requirements.txt"

echo "Environment ready. Activate it with: source $VENV_DIR/bin/activate"
