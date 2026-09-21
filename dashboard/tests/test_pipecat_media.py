"""The opt-in Pipecat batch adapter keeps the existing voice HTTP contract."""

import io
import wave

import pytest

from voice.media.models import AudioUpload, VoiceTranscript
from voice.media.ports import VoiceMediaPort
from voice.pipecat_media.adapter import (
    FallbackPcmTranscriber,
    PipecatBatchTranscriber,
    PipecatWhisperTranscriber,
    build_pcm_transcriber,
)
from voice.pipecat_media.decoder import decode_recording_to_pcm
from voice.pipecat_media.stt import (
    PipecatGroqSttAdapter,
    PipecatWhisperSttAdapter,
    build_groq_service,
)
from voice.pipeline import VoicePipeline, handle_voice_upload


def test_pipecat_transcriber_decodes_upload_then_sends_pcm_to_stt():
    seen = []

    class Stt:
        def transcribe_pcm(self, pcm):
            seen.append(("stt", pcm))
            return "hello Mazda"

    def decode(upload):
        seen.append(("decode", upload.filename, upload.audio_bytes))
        return b"\0\0"

    transcriber = PipecatWhisperTranscriber(Stt(), decode)
    assert transcriber.transcribe(b"webm bytes", "voice.webm") == "hello Mazda"
    assert seen == [("decode", "voice.webm", b"webm bytes"), ("stt", b"\0\0")]


def test_batch_transcriber_is_named_for_its_interface_instead_of_one_provider():
    transcriber = PipecatBatchTranscriber(
        type("Stt", (), {"transcribe_pcm": lambda self, pcm: "heard"})(),
        lambda upload: b"\0\0",
    )
    assert transcriber.transcribe(b"webm bytes", "voice.webm") == "heard"


def test_groq_stt_wraps_pcm_in_a_valid_16khz_mono_wav():
    client_closed = []

    class Transcript:
        def __init__(self, text):
            self.text = text

    class Service:
        class Client:
            async def close(self):
                client_closed.append(True)

        _client = Client()

        async def run_stt(self, audio):
            with wave.open(io.BytesIO(audio), "rb") as wav:
                assert wav.getnchannels() == 1
                assert wav.getsampwidth() == 2
                assert wav.getframerate() == 16000
                assert wav.readframes(wav.getnframes()) == b"\x01\x00\x02\x00"
            yield Transcript("Toyota voice pilot is ready.")

    stt = PipecatGroqSttAdapter(
        lambda: Service(), transcript_type=Transcript, error_type=()
    )
    assert stt.transcribe_pcm(b"\x01\x00\x02\x00") == "Toyota voice pilot is ready."
    assert client_closed == [True]


def test_fallback_pcm_transcriber_uses_local_only_when_groq_fails():
    calls = []
    failures = []

    class Primary:
        def transcribe_pcm(self, pcm):
            calls.append(("groq", pcm))
            raise RuntimeError("network unavailable")

    class Fallback:
        def transcribe_pcm(self, pcm):
            calls.append(("local", pcm))
            return "local result"

    class Observer:
        def observe(self, error):
            failures.append(str(error))

    transcriber = FallbackPcmTranscriber(Primary(), Fallback(), Observer())
    assert transcriber.transcribe_pcm(b"\0\0") == "local result"
    assert calls == [("groq", b"\0\0"), ("local", b"\0\0")]
    assert failures == ["network unavailable"]


def test_fallback_pcm_transcriber_does_not_load_local_after_groq_succeeds():
    class Primary:
        def transcribe_pcm(self, pcm):
            return "fast result"

    class Fallback:
        def transcribe_pcm(self, pcm):
            raise AssertionError("local fallback should stay cold")

    assert FallbackPcmTranscriber(Primary(), Fallback()).transcribe_pcm(b"\0\0") == "fast result"


def test_pcm_factory_selects_groq_with_local_fallback(monkeypatch):
    from voice import config
    from voice.pipecat_media import adapter

    groq = object()
    local = object()
    monkeypatch.setattr(config, "PIPECAT_STT_PROVIDER", "groq")
    monkeypatch.setattr(adapter, "PipecatGroqSttAdapter", lambda: groq)
    monkeypatch.setattr(adapter, "PipecatWhisperSttAdapter", lambda: local)

    selected = build_pcm_transcriber()
    assert isinstance(selected, FallbackPcmTranscriber)
    assert selected.primary is groq
    assert selected.fallback is local


def test_pcm_factory_rejects_unknown_provider(monkeypatch):
    from voice import config

    monkeypatch.setattr(config, "PIPECAT_STT_PROVIDER", "typo")
    with pytest.raises(ValueError, match="unsupported Pipecat STT provider"):
        build_pcm_transcriber()


def test_groq_service_requires_an_api_key(monkeypatch):
    from voice import config

    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        build_groq_service()


def test_groq_service_uses_fast_model_english_and_vocabulary_prompt(monkeypatch):
    import asyncio

    from pipecat.transcriptions.language import Language
    from voice import config

    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "PIPECAT_GROQ_MODEL", "whisper-large-v3-turbo")
    monkeypatch.setattr(config, "WHISPER_PROMPT", "Agent names: Toyota.")

    service = build_groq_service()
    assert service._settings.model == "whisper-large-v3-turbo"
    assert service._settings.language == Language.EN
    assert service._settings.prompt == "Agent names: Toyota."
    assert service._settings.temperature == 0.0
    asyncio.run(service._client.close())


def test_pipecat_pipeline_preserves_voice_media_port_and_cleanup_fallback():
    class Transcriber:
        def transcribe(self, audio, filename):
            assert (audio, filename) == (b"recorded", "voice.mp4")
            return "raw words"

    class Cleanup:
        def clean(self, text):
            return ""

    pipeline = VoicePipeline(Transcriber(), Cleanup())
    assert isinstance(pipeline, VoiceMediaPort)
    assert pipeline.process(AudioUpload(audio_bytes=b"recorded", filename="voice.mp4")) == VoiceTranscript(
        raw_transcript="raw words", cleaned_text="raw words"
    )
    assert handle_voice_upload(pipeline, b"recorded", "voice.mp4") == {
        "ok": True, "raw_transcript": "raw words", "cleaned_text": "raw words"
    }


def test_pipecat_stt_collects_transcription_frames_and_ignores_other_frames():
    class Transcript:
        def __init__(self, text):
            self.text = text

    class Other:
        pass

    class Service:
        async def run_stt(self, pcm):
            assert pcm == b"\0\0"
            yield Other()
            yield Transcript("  final ")
            yield Transcript("words  ")

    stt = PipecatWhisperSttAdapter(
        lambda: Service(), transcript_type=Transcript, error_type=()
    )
    assert stt.transcribe_pcm(b"\0\0") == "final words"


def test_pipecat_stt_rejects_empty_or_error_results():
    class Transcript:
        def __init__(self, text):
            self.text = text
            self.finalized = True

    class Error:
        def __init__(self, error):
            self.error = error

    class EmptyService:
        async def run_stt(self, pcm):
            yield Transcript("   ")

    class ErrorService:
        async def run_stt(self, pcm):
            yield Error("model failed")

    with pytest.raises(ValueError, match="empty transcript"):
        PipecatWhisperSttAdapter(
            lambda: EmptyService(), transcript_type=Transcript, error_type=()
        ).transcribe_pcm(b"\0\0")
    with pytest.raises(RuntimeError, match="model failed"):
        PipecatWhisperSttAdapter(
            lambda: ErrorService(), transcript_type=Transcript, error_type=Error
        ).transcribe_pcm(b"\0\0")


def test_decoder_uses_validated_filename_and_returns_16khz_mono_pcm():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        assert args[args.index("-i") + 1].endswith(".mp4")
        return type("Result", (), {"stdout": b"\0\0", "returncode": 0})()

    upload = AudioUpload(audio_bytes=b"recorded", filename="voice.mp4")
    assert decode_recording_to_pcm(upload, ffmpeg_path="ffmpeg", runner=runner) == b"\0\0"
    args, _ = calls[0]
    assert args[args.index("-ar") + 1] == "16000"
    assert args[args.index("-ac") + 1] == "1"
    assert args[args.index("-f") + 1] == "s16le"


def test_decoder_fails_closed_on_ffmpeg_error():
    def runner(args, **kwargs):
        raise OSError("ffmpeg missing")

    with pytest.raises(RuntimeError, match="decode"):
        decode_recording_to_pcm(
            AudioUpload(audio_bytes=b"recorded"), ffmpeg_path="missing", runner=runner
        )


def test_decoder_rejects_empty_pcm():
    def runner(args, **kwargs):
        return type("Result", (), {"stdout": b""})()

    with pytest.raises(ValueError, match="valid PCM"):
        decode_recording_to_pcm(AudioUpload(audio_bytes=b"recorded"), runner=runner)


def test_factory_selects_pipecat_only_when_requested(monkeypatch):
    from voice import pipeline
    from voice.pipecat_media import adapter

    class Transcriber:
        def transcribe(self, audio, filename):
            return "heard"

    class Cleanup:
        def clean(self, text):
            return text

    current = Transcriber()
    pipecat = Transcriber()
    monkeypatch.setattr(pipeline, "_pipeline", None)
    monkeypatch.setattr(pipeline, "_pipecat_pipeline", None)
    monkeypatch.setattr(pipeline, "build_transcriber", lambda: current)
    monkeypatch.setattr(adapter, "build_pipecat_transcriber", lambda: pipecat)
    monkeypatch.setattr(pipeline, "build_cleanup", lambda: Cleanup())

    assert pipeline.build_pipeline().transcriber is current
    assert pipeline.build_pipeline("pipecat").transcriber is pipecat


def test_factory_rejects_unknown_backend(monkeypatch):
    from voice import pipeline

    with pytest.raises(ValueError, match="unsupported voice media backend"):
        pipeline.build_pipeline("typo")


def test_pinned_pipecat_frame_types_are_read_without_running_a_model():
    pytest.importorskip("pipecat.frames.frames")
    from pipecat.frames.frames import ErrorFrame, TranscriptionFrame

    class Service:
        async def run_stt(self, pcm):
            yield TranscriptionFrame("hello", "dashboard", "2026-09-20T00:00:00Z")

    assert PipecatWhisperSttAdapter(
        lambda: Service(), transcript_type=TranscriptionFrame, error_type=ErrorFrame
    ).transcribe_pcm(b"\0\0") == "hello"


def test_pinned_pipecat_whisper_service_accepts_pcm(monkeypatch):
    pytest.importorskip("pipecat.services.whisper.stt")
    from pipecat.services.whisper.stt import WhisperSTTService
    from voice.pipecat_media.stt import build_whisper_service

    class Segment:
        text = " hello Mazda "
        no_speech_prob = 0.0

    class Model:
        def transcribe(self, audio, **kwargs):
            return [Segment()], None

    def load(self):
        self._model = Model()

    monkeypatch.setattr(WhisperSTTService, "_load", load)
    service = build_whisper_service()
    adapter = PipecatWhisperSttAdapter(lambda: service)
    assert adapter.transcribe_pcm(b"\0\0" * 1000) == "hello Mazda"
    assert adapter.transcribe_pcm(b"\0\0" * 1000) == "hello Mazda"


def test_voice_route_uses_pipecat_only_for_enabled_pilot_agent(monkeypatch):
    from http_app import post_routes
    from voice import config, pipeline

    class Handler:
        headers = {
            "X-Filename": "voice.webm",
            "X-Voice-Media-Backend": "pipecat",
            "X-Voice-Agent-Id": "agent-pilot",
        }

        def json_response(self, result):
            return result

    calls = []
    monkeypatch.setattr(config, "PIPECAT_PILOT_AGENT_ID", "agent-pilot", raising=False)
    monkeypatch.setattr(pipeline, "build_pipeline", lambda *args: calls.append(args) or object())
    monkeypatch.setattr(pipeline, "handle_voice_upload", lambda *args: {"ok": False, "error": "test"})
    assert post_routes.PostRoutesMixin._handle_voice(Handler(), b"recorded") == {
        "ok": False, "error": "test"
    }
    assert calls == [("pipecat",)]

    Handler.headers["X-Voice-Agent-Id"] = "another-agent"
    assert post_routes.PostRoutesMixin._handle_voice(Handler(), b"recorded")["ok"] is False
    assert calls == [("pipecat",)]

    Handler.headers["X-Voice-Agent-Id"] = "agent-pilot"
    monkeypatch.setattr(config, "PIPECAT_PILOT_AGENT_ID", None)
    assert post_routes.PostRoutesMixin._handle_voice(Handler(), b"recorded")["ok"] is False
    assert calls == [("pipecat",)]


def test_voice_route_defaults_to_existing_media_path(monkeypatch):
    from http_app import post_routes
    from voice import pipeline

    class Handler:
        headers = {"X-Filename": "voice.webm"}

        def json_response(self, result):
            return result

    calls = []
    monkeypatch.setattr(pipeline, "build_pipeline", lambda *args: calls.append(args) or object())
    monkeypatch.setattr(pipeline, "handle_voice_upload", lambda *args: {"ok": False, "error": "test"})
    post_routes.PostRoutesMixin._handle_voice(Handler(), b"recorded")
    assert calls == [()]
