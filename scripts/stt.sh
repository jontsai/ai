#!/usr/bin/env bash
set -euo pipefail

# Transcribe speech/in.wav -> speech/out.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
cd "$REPO_ROOT"

IN="$(pwd)/${1:-speech/buffer/in.wav}"
OUT="$(pwd)/${2:-speech/buffer/out.txt}"

if [[ ! -f "$IN" ]]; then
  echo "ERROR: Input file not found: $IN" >&2
  echo "Run 'make listen' first to record audio." >&2
  exit 1
fi

cd speech && ./../scripts/speech-venv.sh run stt.py "$IN" "$OUT"
