#!/usr/bin/env bash
set -euo pipefail

# Speak text from argument or stdin
# Usage:
#   ./scripts/say.sh "Hello world"
#   echo "Hello world" | ./scripts/say.sh
#   ./scripts/say.sh < file.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
cd "$REPO_ROOT"

# Get text from argument or stdin
if [[ $# -gt 0 ]]; then
  TEXT="$*"
else
  TEXT="$(cat)"
fi

if [[ -z "$TEXT" ]]; then
  echo "Usage: $0 <text>" >&2
  echo "   or: echo 'text' | $0" >&2
  exit 1
fi

# Write to temp file, synthesize, play, cleanup
TMP_TXT="$(mktemp)"
TMP_WAV="$(mktemp).wav"
trap 'rm -f "$TMP_TXT" "$TMP_WAV"' EXIT

echo "$TEXT" > "$TMP_TXT"
cd speech && ./../scripts/speech-venv.sh run tts.py "$TMP_TXT" "$TMP_WAV" >/dev/null

# Play audio (macOS)
afplay "$TMP_WAV"
