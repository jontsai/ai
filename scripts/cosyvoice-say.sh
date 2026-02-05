#!/usr/bin/env bash
set -euo pipefail

# CosyVoice TTS - speak text using CosyVoice
# Usage: ./scripts/cosyvoice-say.sh "你好世界" [voice_prompt]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
COSYVOICE_DIR="$REPO_ROOT/speech/cosyvoice"
VENV_DIR="$COSYVOICE_DIR/.venv"

TEXT="${1:-}"
VOICE="${2:-}"  # Optional: path to voice prompt wav, or preset name

if [[ -z "$TEXT" ]]; then
  echo "Usage: $0 <text> [voice_prompt]"
  echo ""
  echo "Examples:"
  echo "  $0 '你好，世界！'"
  echo "  $0 '你好' ./my_voice.wav"
  exit 1
fi

# Check if venv exists
if [[ ! -d "$VENV_DIR" ]]; then
  echo "ERROR: CosyVoice not set up. Run: make cosyvoice-setup"
  exit 1
fi

# Activate venv and run
source "$VENV_DIR/bin/activate"

# Create temp file for output
TMP_WAV="$(mktemp).wav"
trap 'rm -f "$TMP_WAV"' EXIT

cd "$COSYVOICE_DIR"

python - "$TEXT" "$VOICE" "$TMP_WAV" << 'PYTHON_SCRIPT'
import sys
import os

# Add paths
sys.path.insert(0, 'third_party/Matcha-TTS')

text = sys.argv[1]
voice = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
output_path = sys.argv[3]

from cosyvoice.cli.cosyvoice import AutoModel
import torchaudio

# Load model
model_dir = 'pretrained_models/CosyVoice2-0.5B'
if not os.path.exists(model_dir):
    print(f"ERROR: Model not found at {model_dir}")
    print("Run: make cosyvoice-model")
    sys.exit(1)

print("Loading CosyVoice model...", file=sys.stderr)
cosyvoice = AutoModel(model_dir=model_dir)

# Generate speech
print(f"Generating speech for: {text[:50]}...", file=sys.stderr)

if voice and os.path.exists(voice):
    # Zero-shot with voice prompt
    prompt_text = "希望你以后能够做的比我还好呦。"  # Default prompt text
    for i, j in enumerate(cosyvoice.inference_zero_shot(text, prompt_text, voice)):
        torchaudio.save(output_path, j['tts_speech'], cosyvoice.sample_rate)
        break  # Only need first chunk for non-streaming
else:
    # Use cross-lingual mode with language tag
    # Detect language from text
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        tagged_text = f'<|zh|>{text}'
    elif any('\u3040' <= c <= '\u30ff' for c in text):
        tagged_text = f'<|ja|>{text}'
    elif any('\uac00' <= c <= '\ud7af' for c in text):
        tagged_text = f'<|ko|>{text}'
    else:
        tagged_text = f'<|en|>{text}'

    # Use default prompt audio
    prompt_wav = './asset/zero_shot_prompt.wav'
    if os.path.exists(prompt_wav):
        for i, j in enumerate(cosyvoice.inference_cross_lingual(tagged_text, prompt_wav)):
            torchaudio.save(output_path, j['tts_speech'], cosyvoice.sample_rate)
            break
    else:
        print(f"ERROR: Default prompt not found at {prompt_wav}", file=sys.stderr)
        sys.exit(1)

print(f"Saved to {output_path}", file=sys.stderr)
PYTHON_SCRIPT

# Play the audio
afplay "$TMP_WAV"
