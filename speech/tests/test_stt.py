import types
import stt


class FakeInfo:
    language = "en"
    language_probability = 0.99


class FakeSeg:
    def __init__(self, text):
        self.text = text
        self.start = 0.0
        self.end = 1.0


class FakeWhisperModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, audio_path, vad_filter=True):
        segments = [FakeSeg(" hello "), FakeSeg("world")]
        return segments, FakeInfo()


def test_transcribe_to_text(monkeypatch, tmp_path):
    # Patch WhisperModel constructor used by module
    monkeypatch.setattr(stt, "WhisperModel", FakeWhisperModel)

    out = tmp_path / "out.txt"
    summary = stt.transcribe_to_file("in.wav", str(out))

    assert out.read_text(encoding="utf-8") == "hello\nworld\n"
    assert "lang=en" in summary