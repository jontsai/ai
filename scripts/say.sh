#!/usr/bin/env bash
set -euo pipefail

# Speak text from argument or stdin
# Usage:
#   ./scripts/say.sh "Hello world"
#   ./scripts/say.sh -v bf_emma -s 1.2 "Hello world"
#   echo "Hello world" | ./scripts/say.sh
#   echo "Hello world" | ./scripts/say.sh -v am_adam

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
cd "$REPO_ROOT"

# Defaults (can override via env or flags)
VOICE="${VOICE:-af_heart}"
SPEED="${SPEED:-1.0}"

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--voice)
      VOICE="$2"
      shift 2
      ;;
    -s|--speed)
      SPEED="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [-v VOICE] [-s SPEED] [text]"
      echo "       echo 'text' | $0 [-v VOICE] [-s SPEED]"
      echo ""
      echo "Options:"
      echo "  -v, --voice   Voice ID (default: af_heart)"
      echo "  -s, --speed   Speed multiplier (default: 1.0)"
      echo ""
      echo "Popular voices:"
      echo "  American: af_heart, af_bella, af_sarah, am_adam, am_michael"
      echo "  British:  bf_emma, bf_alice, bm_george, bm_daniel"
      echo "  Japanese: jf_alpha, jm_kumo"
      echo "  Chinese:  zf_xiaoxiao, zm_yunxi"
      echo ""
      echo "Full list: cat speech/voices/README.md"
      echo "Demo all:  make voice-demo"
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

# Get text from remaining args or stdin
if [[ $# -gt 0 ]]; then
  TEXT="$*"
else
  TEXT="$(cat)"
fi

if [[ -z "$TEXT" ]]; then
  echo "Usage: $0 [-v VOICE] [-s SPEED] <text>" >&2
  echo "   or: echo 'text' | $0 [-v VOICE] [-s SPEED]" >&2
  exit 1
fi

# Write to temp file, synthesize, play, cleanup
TMP_TXT="$(mktemp)"
TMP_WAV="$(mktemp).wav"
trap 'rm -f "$TMP_TXT" "$TMP_WAV"' EXIT

echo "$TEXT" > "$TMP_TXT"
cd speech && ./../scripts/speech-venv.sh run tts.py -v "$VOICE" -s "$SPEED" "$TMP_TXT" "$TMP_WAV" >/dev/null

# Play audio (macOS)
afplay "$TMP_WAV"
