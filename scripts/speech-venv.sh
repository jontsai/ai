#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
VENV_DIR=".venv"

# Find a stable Python version (3.10-3.13 are well supported; 3.14 has compatibility issues)
find_python() {
  for py in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$py" >/dev/null 2>&1; then
      echo "$py"
      return
    fi
  done
  # Fall back to python3 if no specific version found
  echo "python3"
}

PYTHON_CMD="$(find_python)"

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "==> Creating venv with $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

# Check if requirements are installed by testing a key package
deps_installed() {
  python -c "import textual" 2>/dev/null
}

# Check system dependencies before pip install
check_system_deps() {
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ERROR: ffmpeg not found (required for speech features)"
    echo "  Install: brew install ffmpeg"
    exit 1
  fi
  if ! command -v espeak-ng >/dev/null 2>&1; then
    echo "ERROR: espeak-ng not found (required for non-English TTS)"
    echo "  Install: brew install espeak-ng"
    exit 1
  fi
}

# Ensure venv exists AND dependencies are installed
ensure_deps() {
  ensure_venv
  if ! deps_installed; then
    check_system_deps
    echo "==> Auto-installing speech dependencies (first run)..."
    python -m pip install --upgrade pip -q
    python -m pip install -r requirements.txt -q
  fi
}

install_base() {
  ensure_venv
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

install_dev() {
  # Only install dev/test dependencies, not full requirements.txt
  # This allows tests to run without kokoro (which has Python 3.14 compatibility issues)
  ensure_venv
  python -m pip install --upgrade pip
  python -m pip install -r requirements-dev.txt
}

run_py() {
  ensure_deps
  shift
  python "$@"
}

run_cmd() {
  ensure_deps
  shift
  "$@"
}

case "$ACTION" in
  install) install_base ;;
  install-dev) install_dev ;;
  run) run_py "$@" ;;
  cmd) run_cmd "$@" ;;
  *)
    echo "Usage: $0 install | install-dev | run <script.py> [args...] | cmd <command...>"
    exit 1
    ;;
esac