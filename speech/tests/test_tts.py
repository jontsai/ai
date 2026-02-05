import numpy as np
import tts


def fake_pipeline(text, voice):
    # Yield the tuple shape your tts.py expects: (gs, ps, audio)
    # We'll return two small chunks.
    yield None, None, np.array([0.0, 0.1, 0.2], dtype=np.float32)
    yield None, None, np.array([0.2, 0.1, 0.0], dtype=np.float32)


def test_tts_writes_wav(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "pipeline", fake_pipeline)

    text_path = tmp_path / "in.txt"
    text_path.write_text("hello", encoding="utf-8")

    wav_path = tmp_path / "out.wav"
    tts.tts_file(str(text_path), str(wav_path))

    assert wav_path.exists()
    assert wav_path.stat().st_size > 44  # basic WAV header size