"""TDD: VoicePipeline composition + the /api/voice request handler."""
from voice.pipeline import VoicePipeline, handle_voice_upload


class FakeTranscriber:
    def __init__(self, text):
        self.text = text

    def transcribe(self, audio_bytes, filename="audio.webm"):
        return self.text


class FakeCleanup:
    def __init__(self, mapping=None, raise_=False):
        self.mapping = mapping or {}
        self.raise_ = raise_

    def clean(self, transcript):
        if self.raise_:
            raise RuntimeError("cleanup down")
        return self.mapping.get(transcript, transcript)


def test_pipeline_returns_raw_and_cleaned():
    pipe = VoicePipeline(
        FakeTranscriber("Tell Friday about this."),
        FakeCleanup({"Tell Friday about this.": "Tell Frita about this."}),
    )
    out = pipe.process(b"audio")
    assert out["raw_transcript"] == "Tell Friday about this."
    assert out["cleaned_text"] == "Tell Frita about this."


def test_pipeline_cleanup_failure_falls_back_to_raw():
    pipe = VoicePipeline(FakeTranscriber("raw words"), FakeCleanup(raise_=True))
    out = pipe.process(b"audio")
    assert out["cleaned_text"] == "raw words"


def test_handle_voice_upload_ok():
    class P:
        def process(self, audio, filename="audio.webm"):
            return {"raw_transcript": "r", "cleaned_text": "c"}

    res = handle_voice_upload(P(), b"audio-bytes")
    assert res["ok"] is True
    assert res["cleaned_text"] == "c"
    assert res["raw_transcript"] == "r"


def test_handle_voice_upload_rejects_empty():
    class P:
        def process(self, *a, **k):
            raise AssertionError("must not transcribe empty upload")

    res = handle_voice_upload(P(), b"")
    assert res["ok"] is False
    assert "error" in res


def test_handle_voice_upload_reports_pipeline_error():
    class P:
        def process(self, *a, **k):
            raise RuntimeError("whisper down")

    res = handle_voice_upload(P(), b"audio")
    assert res["ok"] is False
    assert "whisper down" in res["error"]
