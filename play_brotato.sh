#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ "${1:-}" = "--install-shortcut" ]; then
  shift
  if [ -x ".venv/bin/python" ]; then
    .venv/bin/python scripts/create_linux_shortcut.py --game-dir "$(pwd)"
  else
    python3 scripts/create_linux_shortcut.py --game-dir "$(pwd)"
  fi
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[Brotato Python] Python 3 is missing."
  if command -v apt-get >/dev/null 2>&1; then
    echo "[Brotato Python] Installing Python 3 via apt..."
    sudo apt-get update -qq && sudo apt-get install -y python3 python3-venv python3-pip
  else
    echo "Please install Python 3.11+ first."
    exit 1
  fi
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[Brotato Python] First-time setup: creating .venv and installing pygame-ce + numpy..."
  if ! python3 -c "import ensurepip, venv" >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      echo "[Brotato Python] Linux Mint/Ubuntu requires python3-venv for isolated setup. Installing via apt..."
      sudo apt-get update -qq && sudo apt-get install -y python3-venv python3-pip
    else
      echo "[Brotato Python] Error: python3 venv/ensurepip is missing. Install your distro's python3-venv package."
      exit 1
    fi
  fi
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip -q
  .venv/bin/python -m pip install "pygame-ce>=2.5.0" "numpy>=1.26.0" -q
fi

echo "[Brotato Python] Launching game..."
exec .venv/bin/python main.py "$@"
