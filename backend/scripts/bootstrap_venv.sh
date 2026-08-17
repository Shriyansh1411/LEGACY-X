#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a Python virtual environment in backend/.venv and install requirements
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -x "$(command -v python3)" ]; then
  echo "python3 is required but not found. Please install Python 3." >&2
  exit 1
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements.txt"

echo "Virtualenv created and dependencies installed in $VENV_DIR"
