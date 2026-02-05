#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-record}"

# You can override these:
DURATION="${DURATION:-10}"
OUT="speech/in.wav"

# Choose mic by index. If you don't set MIC, we default to ":0" (often default audio input).
# List devices first to be sure:
#   ./scripts/record.sh devices
MIC="${MIC:-:0}"

devices() {
  # Lists devices; helpful to find the right mic index.
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | sed -n '1,200p'
}

record() {
  mkdir -p speech
  echo "Recording ${DURATION}s from avfoundation input '${MIC}' -> ${OUT}"
  echo "Tip: set MIC=':1' (or similar) after running: ./scripts/record.sh devices"
  ffmpeg -hide_banner -loglevel error \
    -f avfoundation -i "${MIC}" \
    -t "${DURATION}" \
    -ac 1 -ar 16000 \
    "${OUT}"
  echo "Wrote ${OUT}"
}

case "$MODE" in
  devices) devices ;;
  record) record ;;
  *)
    echo "Usage: $0 devices|record"
    exit 1
    ;;
esac