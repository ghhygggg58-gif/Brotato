#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[Brotato Python] Python 3.11+ was not found. Please install Python 3 first."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[Brotato Python] First-time setup: creating .venv and installing pygame-ce + numpy..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install "pygame-ce>=2.5.0" "numpy>=1.26.0"
fi

echo "[Brotato Python] Launching game..."
exec .venv/bin/python main.py "$@"
