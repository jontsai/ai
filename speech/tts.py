#!/usr/bin/env python3
"""
Text-to-Speech using Kokoro.

Supports two backends:
  - "onnx": kokoro-onnx (default, works on Python 3.13+)
  - "native": kokoro (requires spacy, currently broken on Python 3.13+)

Set TTS_BACKEND=native to use the native backend when it becomes available.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0

# Language metadata for voice prefixes
# Maps voice prefix -> (lang_code, nationality)
# lang_code uses espeak-ng codes (e.g., 'cmn' for Mandarin, not 'zh')
VOICE_LANG_META = {
    "a": ("en-us", "American"),
    "b": ("en-gb", "British"),
    "j": ("ja", "Japanese"),
    "z": ("cmn", "Chinese"),
    "e": ("es", "Spanish"),
    "f": ("fr-fr", "French"),
    "h": ("hi", "Hindi"),
    "i": ("it", "Italian"),
    "p": ("pt-br", "Brazilian Portuguese"),
}


def get_article(word: str) -> str:
    """Return 'an' if word starts with a vowel sound, else 'a'."""
    if not word:
        return "a"
    return "an" if word[0].lower() in "aeiou" else "a"


def _lang_from_voice(voice: str) -> str:
    """Infer language code from voice ID (e.g., 'zf_xiaobei' -> 'cmn')."""
    if voice and len(voice) >= 1:
        prefix = voice[0].lower()
        meta = VOICE_LANG_META.get(prefix)
        return meta[0] if meta else "en-us"
    return "en-us"

# Backend selection: "onnx" (default) or "native"
TTS_BACKEND = os.environ.get("TTS_BACKEND", "onnx")

# Model paths for ONNX backend (relative to this file's directory)
_SCRIPT_DIR = Path(__file__).parent
_MODEL_DIR = _SCRIPT_DIR / "models"
_ONNX_MODEL = _MODEL_DIR / "kokoro-v1.0.onnx"
_VOICES_BIN = _MODEL_DIR / "voices-v1.0.bin"

# Lazy-loaded instances
_onnx_instance = None
_native_pipeline = None


# -----------------------------------------------------------------------------
# ONNX Backend (kokoro-onnx)
# -----------------------------------------------------------------------------

def _get_onnx_instance():
    """Lazy-load the Kokoro ONNX model."""
    global _onnx_instance
    if _onnx_instance is None:
        from kokoro_onnx import Kokoro
        if not _ONNX_MODEL.exists() or not _VOICES_BIN.exists():
            raise FileNotFoundError(
                f"ONNX model files not found. Download them:\n"
                f"  mkdir -p {_MODEL_DIR}\n"
                f"  wget -P {_MODEL_DIR} https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx\n"
                f"  wget -P {_MODEL_DIR} https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
            )
        _onnx_instance = Kokoro(str(_ONNX_MODEL), str(_VOICES_BIN))
    return _onnx_instance


def _synthesize_onnx(text: str, voice: str = DEFAULT_VOICE, lang: str | None = None, speed: float = DEFAULT_SPEED):
    """Synthesize speech using kokoro-onnx."""
    kokoro = _get_onnx_instance()
    # Auto-detect language from voice if not specified
    if lang is None:
        lang = _lang_from_voice(voice)
    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    return np.asarray(samples, dtype=np.float32), sample_rate


# -----------------------------------------------------------------------------
# CosyVoice Backend (high-quality Chinese TTS)
# -----------------------------------------------------------------------------

# Path to CosyVoice setup
_COSYVOICE_DIR = _SCRIPT_DIR / "cosyvoice"
_COSYVOICE_VENV = _COSYVOICE_DIR / ".venv"
_COSYVOICE_MODEL = _COSYVOICE_DIR / "pretrained_models" / "CosyVoice2-0.5B"

# Daemon settings
_COSYVOICE_DAEMON_HOST = os.environ.get("COSYVOICE_HOST", "127.0.0.1")
_COSYVOICE_DAEMON_PORT = int(os.environ.get("COSYVOICE_PORT", "8765"))


def _is_cosyvoice_available() -> bool:
    """Check if CosyVoice is set up and ready."""
    return _COSYVOICE_VENV.exists() and _COSYVOICE_MODEL.exists()


def _is_cosyvoice_daemon_running() -> bool:
    """Check if the CosyVoice daemon is running."""
    import urllib.request
    import urllib.error
    try:
        url = f"http://{_COSYVOICE_DAEMON_HOST}:{_COSYVOICE_DAEMON_PORT}/health"
        with urllib.request.urlopen(url, timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _synthesize_cosyvoice_daemon(text: str, lang: str = "zh") -> tuple:
    """Synthesize using the CosyVoice daemon (fast path)."""
    import urllib.request
    import json

    url = f"http://{_COSYVOICE_DAEMON_HOST}:{_COSYVOICE_DAEMON_PORT}/synthesize"
    data = json.dumps({"text": text, "lang": lang}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        wav_bytes = resp.read()

    # Parse WAV bytes
    import io
    samples, sample_rate = sf.read(io.BytesIO(wav_bytes))
    return np.asarray(samples, dtype=np.float32), sample_rate


def _synthesize_cosyvoice_subprocess(text: str) -> tuple:
    """Synthesize using subprocess (slow path, loads model each time)."""
    # Create temp file for output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = f.name

    try:
        # Build the Python script to run in CosyVoice venv
        python_script = f'''
import sys
sys.path.insert(0, 'third_party/Matcha-TTS')
from cosyvoice.cli.cosyvoice import AutoModel
import torchaudio

cosyvoice = AutoModel(model_dir='pretrained_models/CosyVoice2-0.5B')

# Add language tag for Chinese
text = '<|zh|>' + {repr(text)}

for i, j in enumerate(cosyvoice.inference_cross_lingual(text, './asset/zero_shot_prompt.wav')):
    torchaudio.save({repr(output_path)}, j['tts_speech'], cosyvoice.sample_rate)
    break
'''

        # Run in CosyVoice venv
        python_bin = _COSYVOICE_VENV / "bin" / "python"
        result = subprocess.run(
            [str(python_bin), "-c", python_script],
            cwd=str(_COSYVOICE_DIR),
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for model loading + synthesis
        )

        if result.returncode != 0:
            raise RuntimeError(f"CosyVoice failed: {result.stderr}")

        # Read the generated audio
        samples, sample_rate = sf.read(output_path)
        return np.asarray(samples, dtype=np.float32), sample_rate

    finally:
        # Clean up temp file
        if os.path.exists(output_path):
            os.unlink(output_path)


def _synthesize_cosyvoice(text: str, voice: str = "zh_female", speed: float = DEFAULT_SPEED):
    """
    Synthesize speech using CosyVoice (for Chinese).

    Tries daemon first (fast), falls back to subprocess (slow).
    """
    if not _is_cosyvoice_available():
        raise FileNotFoundError(
            "CosyVoice not set up. Run: make cosyvoice-setup"
        )

    # Try daemon first (fast path)
    if _is_cosyvoice_daemon_running():
        return _synthesize_cosyvoice_daemon(text, lang="zh")

    # Fall back to subprocess (slow path)
    return _synthesize_cosyvoice_subprocess(text)


# -----------------------------------------------------------------------------
# Native Backend (kokoro with spacy) - for future use
# -----------------------------------------------------------------------------

def _get_native_pipeline():
    """Lazy-load the native KPipeline."""
    global _native_pipeline
    if _native_pipeline is None:
        from kokoro import KPipeline
        _native_pipeline = KPipeline(lang_code="a")  # American English
    return _native_pipeline


def _synthesize_native(text: str, voice: str = DEFAULT_VOICE, lang: str | None = None, speed: float = DEFAULT_SPEED):
    """Synthesize speech using native kokoro (requires spacy)."""
    pipe = _get_native_pipeline()
    chunks = []
    # Note: native kokoro speed control may differ; this is a placeholder
    for _gs, _ps, audio in pipe(text, voice=voice, speed=speed):
        chunks.append(audio)
    if chunks:
        return np.concatenate(chunks), SAMPLE_RATE
    return np.array([], dtype=np.float32), SAMPLE_RATE


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def is_cosyvoice_available() -> bool:
    """Check if CosyVoice backend is available for Chinese TTS."""
    return _is_cosyvoice_available()


def synthesize(text: str, voice: str = DEFAULT_VOICE, lang: str | None = None, speed: float = DEFAULT_SPEED):
    """
    Synthesize speech from text.

    Args:
        text: The text to speak.
        voice: Voice ID (e.g., "af_heart", "zf_xiaobei").
        lang: Language code (e.g., "en-us", "zh"). Auto-detected from voice if None.
        speed: Speed multiplier (0.5 = half, 2.0 = double).

    Returns:
        Tuple of (samples, sample_rate) where samples is a numpy array.
    """
    # Route CosyVoice-specific voice to CosyVoice backend
    if voice and voice.startswith("cosyvoice_") and _is_cosyvoice_available():
        return _synthesize_cosyvoice(text, voice, speed)

    if TTS_BACKEND == "native":
        return _synthesize_native(text, voice, lang, speed)
    else:
        return _synthesize_onnx(text, voice, lang, speed)


def pipeline(text: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED):
    """
    Generate audio chunks for the given text.

    This function exists for API compatibility with tests.
    Yields tuples of (graphemes, phonemes, audio_array).
    """
    samples, _sr = synthesize(text, voice, speed=speed)
    # Yield as a single chunk to match the expected interface
    yield None, None, samples


def tts_file(text_path: str, wav_path: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED) -> None:
    """Convert text file to speech and save as WAV."""
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        raise ValueError("Input text is empty")

    # Use pipeline() to allow test mocking
    chunks = []
    for _gs, _ps, audio in pipeline(text, voice, speed):
        chunks.append(audio)

    if chunks:
        combined = np.concatenate(chunks)
        sf.write(wav_path, combined, SAMPLE_RATE)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Text-to-Speech using Kokoro")
    parser.add_argument("input", help="Input text file")
    parser.add_argument("output", help="Output WAV file")
    parser.add_argument("-v", "--voice", default=DEFAULT_VOICE, help=f"Voice ID (default: {DEFAULT_VOICE})")
    parser.add_argument("-s", "--speed", type=float, default=DEFAULT_SPEED, help=f"Speed multiplier (default: {DEFAULT_SPEED})")
    args = parser.parse_args()

    try:
        tts_file(args.input, args.output, voice=args.voice, speed=args.speed)
        print(f"Wrote {args.output}")
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
