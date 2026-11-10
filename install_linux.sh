#!/usr/bin/env bash
set -euo pipefail

# Easy 1-command installer & launcher for Linux Mint, Ubuntu, Debian, Fedora, and Arch.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ghhygggg58-gif/Brotato/main/install_linux.sh | bash
# Or inside a downloaded folder:
#   bash install_linux.sh

REPO_OWNER="ghhygggg58-gif"
REPO_NAME="Brotato"
BRANCH="main"
INSTALL_DIR="${BROTATO_DIR:-$HOME/Games/Brotato-Python}"
EXPLICIT_DIR=0
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
RUN_AFTER=1
CREATE_SHORTCUT=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      EXPLICIT_DIR=1
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --token)
      TOKEN="$2"
      shift 2
      ;;
    --no-run)
      RUN_AFTER=0
      shift
      ;;
    --no-shortcut)
      CREATE_SHORTCUT=0
      shift
      ;;
    *)
      shift
      ;;
  esac
done

echo "=== Brotato Python - Easy Linux Installer ==="

_install_missing_sys_deps() {
  local need_pkgs=()
  if ! command -v python3 >/dev/null 2>&1; then
    need_pkgs+=("python3")
  fi
  if ! command -v curl >/dev/null 2>&1; then
    need_pkgs+=("curl")
  fi
  if ! command -v unzip >/dev/null 2>&1; then
    need_pkgs+=("unzip")
  fi
  # On Linux Mint / Ubuntu / Debian, python3-venv & python3-pip are often separate packages
  if command -v python3 >/dev/null 2>&1; then
    if ! python3 -c "import ensurepip, venv" >/dev/null 2>&1; then
      need_pkgs+=("python3-venv" "python3-pip")
    fi
  else
    need_pkgs+=("python3-venv" "python3-pip")
  fi

  if [ "${#need_pkgs[@]}" -eq 0 ]; then
    return 0
  fi

  echo "[1/4] Installing required system packages: ${need_pkgs[*]}"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y "${need_pkgs[@]}"
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip curl unzip
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip curl unzip
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y python3 python3-pip curl unzip
  else
    echo "Please install: ${need_pkgs[*]}"
    exit 1
  fi
}

_install_missing_sys_deps

# Detect if already running from inside a cloned/unzipped Brotato directory
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ "$EXPLICIT_DIR" -eq 0 ] && [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/main.py" ] && [ -d "$SCRIPT_DIR/src/brotato" ]; then
  INSTALL_DIR="$SCRIPT_DIR"
  echo "[2/4] Using existing game folder: $INSTALL_DIR"
elif [ "$EXPLICIT_DIR" -eq 0 ] && [ -f "./main.py" ] && [ -d "./src/brotato" ]; then
  INSTALL_DIR="$(pwd)"
  echo "[2/4] Using current game folder: $INSTALL_DIR"
else
  echo "[2/4] Downloading Brotato Python into: $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  TMP_ZIP="$(mktemp /tmp/brotato-XXXXXX.zip)"
  TMP_EXTRACT="$(mktemp -d /tmp/brotato-extract-XXXXXX)"
  trap 'rm -f "$TMP_ZIP"; rm -rf "$TMP_EXTRACT"' EXIT

  DOWNLOADED=0
  if [ -n "$TOKEN" ]; then
    if curl -fsSL -H "Authorization: Bearer $TOKEN" \
      "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/zipball/$BRANCH" -o "$TMP_ZIP"; then
      DOWNLOADED=1
    fi
  fi

  if [ "$DOWNLOADED" -eq 0 ]; then
    if curl -fsSL "https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/heads/$BRANCH.zip" -o "$TMP_ZIP" 2>/dev/null; then
      DOWNLOADED=1
    fi
  fi

  if [ "$DOWNLOADED" -eq 0 ] && command -v gh >/dev/null 2>&1; then
    echo "Public download failed; trying authenticated GitHub CLI (gh)..."
    if gh api "repos/$REPO_OWNER/$REPO_NAME/zipball/$BRANCH" > "$TMP_ZIP" 2>/dev/null; then
      DOWNLOADED=1
    fi
  fi

  if [ "$DOWNLOADED" -eq 0 ]; then
    echo ""
    echo "Could not download repository archive automatically."
    echo "If this repository is private, either:"
    echo "  1) Authenticate once: gh auth login   (then re-run this command)"
    echo "  2) Or pass a token:   GITHUB_TOKEN=your_token bash <(cat)"
    exit 1
  fi

  unzip -q "$TMP_ZIP" -d "$TMP_EXTRACT"
  INNER_DIR="$(find "$TMP_EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  cp -a "$INNER_DIR"/. "$INSTALL_DIR"/
  chmod +x "$INSTALL_DIR/play_brotato.sh" "$INSTALL_DIR/Play_Brotato.command" "$INSTALL_DIR/download_brotato.py" "$INSTALL_DIR/install_linux.sh" 2>/dev/null || true
fi

cd "$INSTALL_DIR"

echo "[3/4] Setting up Python virtual environment & game libraries (pygame-ce + numpy)..."
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install "pygame-ce>=2.5.0" "numpy>=1.26.0" -q

if [ "$CREATE_SHORTCUT" -eq 1 ] && [ -f "scripts/create_linux_shortcut.py" ]; then
  echo "[4/4] Creating Linux Mint Menu & Desktop shortcuts..."
  .venv/bin/python scripts/create_linux_shortcut.py --game-dir "$INSTALL_DIR" || true
else
  echo "[4/4] Skipping shortcuts."
fi

echo ""
echo "============================================"
echo "  Brotato Python is installed and ready!"
echo "  Folder: $INSTALL_DIR"
echo "  Launch anytime:"
echo "    - Double-click 'Brotato' on your Desktop or Mint Games Menu"
echo "    - Or run: ~/.local/bin/brotato"
echo "    - Or run: cd \"$INSTALL_DIR\" && ./play_brotato.sh"
echo "============================================"

if [ "$RUN_AFTER" -eq 1 ]; then
  exec .venv/bin/python main.py
fi
