#!/usr/bin/env python3
import sys

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"

# Lazy imports for testing - allows module to be imported without kokoro installed
_KPipeline = None
_pipeline_instance = None


def _get_kpipeline_class():
    global _KPipeline
    if _KPipeline is None:
        from kokoro import KPipeline
        _KPipeline = KPipeline
    return _KPipeline


def _get_pipeline():
    """Lazy-load the KPipeline instance to avoid startup cost."""
    global _pipeline_instance
    if _pipeline_instance is None:
        KPipeline = _get_kpipeline_class()
        _pipeline_instance = KPipeline(lang_code="a")  # American English
    return _pipeline_instance


def pipeline(text: str, voice: str = DEFAULT_VOICE):
    """Generate audio chunks for the given text.

    Yields:
        Tuples of (graphemes, phonemes, audio_array)
    """
    pipe = _get_pipeline()
    yield from pipe(text, voice=voice)


def tts_file(text_path: str, wav_path: str, voice: str = DEFAULT_VOICE) -> None:
    """Convert text file to speech and save as WAV."""
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    chunks = []
    for _gs, _ps, audio in pipeline(text, voice=voice):
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
    tts_file(text_path, wav_path)
    print(f"Wrote {wav_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())