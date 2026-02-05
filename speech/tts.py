#!/usr/bin/env python3
"""
Text-to-Speech using Kokoro.

Supports two backends:
  - "onnx": kokoro-onnx (default, works on Python 3.13+)
  - "native": kokoro (requires spacy, currently broken on Python 3.13+)

Set TTS_BACKEND=native to use the native backend when it becomes available.
"""
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"
DEFAULT_LANG = "en-us"

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


def _synthesize_onnx(text: str, voice: str = DEFAULT_VOICE, lang: str = DEFAULT_LANG):
    """Synthesize speech using kokoro-onnx."""
    kokoro = _get_onnx_instance()
    samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0, lang=lang)
    return np.asarray(samples, dtype=np.float32), sample_rate


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


def _synthesize_native(text: str, voice: str = DEFAULT_VOICE, lang: str = DEFAULT_LANG):
    """Synthesize speech using native kokoro (requires spacy)."""
    pipe = _get_native_pipeline()
    chunks = []
    for _gs, _ps, audio in pipe(text, voice=voice):
        chunks.append(audio)
    if chunks:
        return np.concatenate(chunks), SAMPLE_RATE
    return np.array([], dtype=np.float32), SAMPLE_RATE


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def synthesize(text: str, voice: str = DEFAULT_VOICE, lang: str = DEFAULT_LANG):
    """
    Synthesize speech from text.

    Args:
        text: The text to speak.
        voice: Voice ID (e.g., "af_heart", "af_sarah").
        lang: Language code (e.g., "en-us").

    Returns:
        Tuple of (samples, sample_rate) where samples is a numpy array.
    """
    if TTS_BACKEND == "native":
        return _synthesize_native(text, voice, lang)
    else:
        return _synthesize_onnx(text, voice, lang)


def pipeline(text: str, voice: str = DEFAULT_VOICE):
    """
    Generate audio chunks for the given text.

    This function exists for API compatibility with tests.
    Yields tuples of (graphemes, phonemes, audio_array).
    """
    samples, _sr = synthesize(text, voice)
    # Yield as a single chunk to match the expected interface
    yield None, None, samples


def tts_file(text_path: str, wav_path: str, voice: str = DEFAULT_VOICE) -> None:
    """Convert text file to speech and save as WAV."""
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        raise ValueError("Input text is empty")

    # Use pipeline() to allow test mocking
    chunks = []
    for _gs, _ps, audio in pipeline(text, voice):
        chunks.append(audio)

    if chunks:
        combined = np.concatenate(chunks)
        sf.write(wav_path, combined, SAMPLE_RATE)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: tts.py <input.txt> <output.wav>", file=sys.stderr)
        return 2

    text_path = sys.argv[1]
    wav_path = sys.argv[2]

    try:
        tts_file(text_path, wav_path)
        print(f"Wrote {wav_path}")
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
