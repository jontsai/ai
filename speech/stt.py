#!/usr/bin/env python3
import sys

# Lazy import for testing - allows module to be imported without faster_whisper installed
WhisperModel = None


def _get_whisper_model_class():
    global WhisperModel
    if WhisperModel is None:
        from faster_whisper import WhisperModel as _WhisperModel
        WhisperModel = _WhisperModel
    return WhisperModel


def transcribe_to_file(audio_path: str, out_path: str) -> str:
    # "large-v3" is excellent quality. int8 reduces memory.
    model_cls = WhisperModel or _get_whisper_model_class()
    model = model_cls("large-v3", device="auto", compute_type="int8")
    segments, info = model.transcribe(audio_path, vad_filter=True)

    lines = []
    for s in segments:
        text = (s.text or "").strip()
        if text:
            lines.append(text)

    text_out = "\n".join(lines).strip() + ("\n" if lines else "")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text_out)

    summary = f"lang={info.language} prob={getattr(info, 'language_probability', 0):.2f} chars={len(text_out)}"
    return summary


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: stt.py <input.wav> <output.txt>", file=sys.stderr)
        return 2

    audio_path = sys.argv[1]
    out_path = sys.argv[2]
    summary = transcribe_to_file(audio_path, out_path)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())