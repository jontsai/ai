#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
VENV_DIR=".venv"

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
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
  ensure_venv
  shift
  python "$@"
}

run_cmd() {
  ensure_venv
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