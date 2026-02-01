#!/usr/bin/env bash
set -euo pipefail

OLLAMA_DIR_MAC="$HOME/Library/Application Support/Ollama"

echo "Ollama storage:"
if [[ -d "$OLLAMA_DIR_MAC" ]]; then
  echo "  $OLLAMA_DIR_MAC"
  du -sh "$OLLAMA_DIR_MAC" || true
else
  echo "  (not found at $OLLAMA_DIR_MAC)"
fi

echo
echo "ollama list:"
ollama list || true

echo
echo "Largest 15 files (best-effort):"
if [[ -d "$OLLAMA_DIR_MAC" ]]; then
  find "$OLLAMA_DIR_MAC" -type f -print0 \
    | xargs -0 ls -lh \
    | sort -k5 -h \
    | tail -n 15
else
  echo "(skipping: Ollama directory not found)"
fi