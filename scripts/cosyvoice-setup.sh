#!/usr/bin/env bash
set -euo pipefail

# CosyVoice setup script for macOS inference
# Creates a separate venv with Python 3.10 and installs minimal dependencies

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
COSYVOICE_DIR="$REPO_ROOT/speech/cosyvoice"
VENV_DIR="$COSYVOICE_DIR/.venv"
MODEL_DIR="$COSYVOICE_DIR/pretrained_models"

ACTION="${1:-help}"

# Find Python 3.10 (required by CosyVoice)
find_python310() {
  for py in python3.10 /opt/homebrew/bin/python3.10 /usr/local/bin/python3.10; do
    if command -v "$py" >/dev/null 2>&1; then
      version=$("$py" --version 2>&1 | grep -oE '3\.10\.[0-9]+')
      if [[ -n "$version" ]]; then
        echo "$py"
        return
      fi
    fi
  done
  echo ""
}

ensure_venv() {
  PYTHON310=$(find_python310)
  if [[ -z "$PYTHON310" ]]; then
    echo "ERROR: Python 3.10 not found (required by CosyVoice)"
    echo "  Install: brew install python@3.10"
    exit 1
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    echo "==> Creating venv with $PYTHON310"
    "$PYTHON310" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

install_deps() {
  ensure_venv
  echo "==> Installing CosyVoice dependencies (this may take a while)..."

  # Upgrade pip
  python -m pip install --upgrade pip -q

  # Install PyTorch for macOS (MPS support)
  echo "==> Installing PyTorch..."
  pip install torch torchaudio -q

  # Install core dependencies for inference
  echo "==> Installing inference dependencies..."
  pip install \
    conformer==0.3.2 \
    diffusers==0.29.0 \
    hydra-core==1.3.2 \
    HyperPyYAML==1.2.2 \
    inflect==7.3.1 \
    librosa==0.10.2 \
    matplotlib==3.7.5 \
    modelscope==1.20.0 \
    omegaconf==2.3.0 \
    onnxruntime==1.18.0 \
    protobuf==4.25 \
    pydantic==2.7.0 \
    rich==13.7.1 \
    soundfile==0.12.1 \
    transformers==4.51.3 \
    wetext==0.0.4 \
    wget==3.2 \
    -q

  # Install pynini via conda-forge if available, otherwise skip
  if command -v conda >/dev/null 2>&1; then
    echo "==> Installing pynini via conda..."
    conda install -y -c conda-forge pynini==2.1.5 2>/dev/null || echo "  (pynini optional, skipping)"
  else
    echo "==> Skipping pynini (conda not available, text normalization will use wetext)"
  fi

  # Add CosyVoice to path
  echo "==> Setting up CosyVoice module..."
  pip install -e "$COSYVOICE_DIR" -q 2>/dev/null || true

  echo "==> Dependencies installed!"
}

download_model() {
  ensure_venv
  mkdir -p "$MODEL_DIR"

  echo "==> Downloading CosyVoice 0.5B model (~2GB)..."
  python -c "
from modelscope import snapshot_download
# ModelScope uses 'iic/' prefix, not 'FunAudioLLM/'
snapshot_download('iic/CosyVoice2-0.5B',
                  local_dir='$MODEL_DIR/CosyVoice2-0.5B')
print('Model downloaded!')
"
}

run_py() {
  ensure_venv
  cd "$COSYVOICE_DIR"
  shift
  python "$@"
}

case "$ACTION" in
  install)
    install_deps
    ;;
  download-model)
    download_model
    ;;
  setup)
    install_deps
    download_model
    ;;
  run)
    run_py "$@"
    ;;
  help|*)
    echo "CosyVoice Setup Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install         Install Python dependencies"
    echo "  download-model  Download pretrained model (~2GB)"
    echo "  setup           Install deps + download model (full setup)"
    echo "  run <script>    Run a Python script in the CosyVoice venv"
    ;;
esac
