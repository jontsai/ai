#!/usr/bin/env bash
set -euo pipefail

# Speak speech/out.txt -> speech/out.wav, then play

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
cd "$REPO_ROOT"

IN="$(pwd)/${1:-speech/buffer/out.txt}"
OUT="$(pwd)/${2:-speech/buffer/out.wav}"

if [[ ! -f "$IN" ]]; then
  echo "ERROR: Input file not found: $IN" >&2
  echo "Run 'make stt' first to transcribe audio, or create a text file." >&2
  exit 1
fi

cd speech && ./../scripts/speech-venv.sh run tts.py "$IN" "$OUT"

# Play the audio (macOS)
if command -v afplay &>/dev/null; then
  afplay "$OUT"
fi
