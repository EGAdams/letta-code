"""Contract for the upload media port and the browser-facing voice response."""

import pytest
from pydantic import ValidationError

from voice.media.models import AudioUpload, VoiceTranscript
from voice.media.ports import VoiceMediaPort
from voice.pipeline import VoicePipeline, handle_voice_upload


@pytest.mark.parametrize("filename", ["voice.webm", "voice.ogg", "voice.mp4", "voice.wav"])
def test_upload_accepts_recorded_audio_formats(filename):
    upload = AudioUpload(audio_bytes=b"recorded", filename=filename)
    assert upload.filename == filename


@pytest.mark.parametrize("filename", ["../voice.webm", "voice.txt", "voice.webm/escape"])
def test_upload_rejects_invalid_or_unsafe_filenames(filename):
    with pytest.raises(ValidationError):
        AudioUpload(audio_bytes=b"recorded", filename=filename)


def test_upload_rejects_empty_audio():
    with pytest.raises(ValidationError):
        AudioUpload(audio_bytes=b"", filename="voice.webm")


def test_existing_pipeline_satisfies_media_port_and_preserves_filename():
    seen = []

    class Transcriber:
        def transcribe(self, audio_bytes, filename):
            seen.append((audio_bytes, filename))
            return "raw words"

    class Cleanup:
        def clean(self, text):
            return "clean words"

    pipeline = VoicePipeline(Transcriber(), Cleanup())
    assert isinstance(pipeline, VoiceMediaPort)
    transcript = pipeline.process(AudioUpload(audio_bytes=b"recorded", filename="voice.mp4"))
    assert transcript == VoiceTranscript(raw_transcript="raw words", cleaned_text="clean words")
    assert seen == [(b"recorded", "voice.mp4")]


def test_empty_cleanup_reply_falls_back_to_raw_transcript():
    class Transcriber:
        def transcribe(self, audio_bytes, filename):
            return "raw words"

    class Cleanup:
        def clean(self, text):
            return ""

    result = VoicePipeline(Transcriber(), Cleanup()).process(
        AudioUpload(audio_bytes=b"recorded"))
    assert result.cleaned_text == "raw words"


def test_upload_response_is_validated_before_it_reaches_browser():
    class MalformedMedia:
        def process(self, upload):
            return {"raw_transcript": "heard", "cleaned_text": None}

    response = handle_voice_upload(MalformedMedia(), b"recorded", "voice.webm")
    assert response["ok"] is False
    assert "error" in response
    assert "cleaned_text" not in response


def test_invalid_filename_never_reaches_media_port():
    class Media:
        def process(self, upload):
            raise AssertionError("invalid upload reached media port")

    response = handle_voice_upload(Media(), b"recorded", "../voice.webm")
    assert response["ok"] is False
