"""TDD: VoicePipeline composition + the /api/voice request handler."""
from voice.pipeline import VoicePipeline, handle_voice_upload
from voice.media.models import AudioUpload, VoiceTranscript


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
    out = pipe.process(AudioUpload(audio_bytes=b"audio"))
    assert out == VoiceTranscript(raw_transcript="Tell Friday about this.", cleaned_text="Tell Frita about this.")


def test_pipeline_cleanup_failure_falls_back_to_raw():
    pipe = VoicePipeline(FakeTranscriber("raw words"), FakeCleanup(raise_=True))
    out = pipe.process(AudioUpload(audio_bytes=b"audio"))
    assert out.cleaned_text == "raw words"


def test_pipeline_reports_transcription_and_cleanup_timings():
    observed = []

    class Observer:
        def observe(self, stage, duration_seconds):
            observed.append((stage, duration_seconds))

    pipe = VoicePipeline(
        FakeTranscriber("raw words"), FakeCleanup(), timing_observer=Observer()
    )
    pipe.process(AudioUpload(audio_bytes=b"audio"))

    assert [stage for stage, _ in observed] == ["transcription", "cleanup"]
    assert all(duration >= 0 for _, duration in observed)


def test_handle_voice_upload_ok():
    class P:
        def process(self, upload):
            return VoiceTranscript(raw_transcript="r", cleaned_text="c")

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
    assert res == {"ok": False, "error": "empty audio upload"}


def test_handle_voice_upload_reports_pipeline_error():
    class P:
        def process(self, *a, **k):
            raise RuntimeError("whisper down")

    res = handle_voice_upload(P(), b"audio")
    assert res["ok"] is False
    assert "whisper down" in res["error"]
