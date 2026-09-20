"""VoicePipeline — composes transcribe -> cleanup, plus the /api/voice handler."""
from pydantic import ValidationError

from .cleanup import build_cleanup
from .media.models import AudioUpload, VoiceTranscript
from .media.ports import VoiceMediaPort
from .transcription import build_transcriber


class VoicePipeline:
    def __init__(self, transcriber, cleanup):
        self.transcriber = transcriber
        self.cleanup = cleanup

    def process(self, upload: AudioUpload) -> VoiceTranscript:
        raw = self.transcriber.transcribe(upload.audio_bytes, upload.filename)
        try:
            cleaned = self.cleanup.clean(raw)
        except Exception:
            cleaned = raw  # belt-and-suspenders; cleanup also falls back internally
        if not cleaned or not cleaned.strip():
            cleaned = raw
        return VoiceTranscript(raw_transcript=raw, cleaned_text=cleaned)


def handle_voice_upload(pipeline: VoiceMediaPort, audio_bytes: bytes,
                        filename: str = "audio.webm") -> dict:
    """Pure request handler — used by server.py's POST /api/voice. JSON-able dict."""
    if not audio_bytes:
        return {"ok": False, "error": "empty audio upload"}
    try:
        upload = AudioUpload(audio_bytes=audio_bytes, filename=filename)
    except ValidationError:
        return {"ok": False, "error": "invalid audio upload"}
    try:
        result = pipeline.process(upload)
        transcript = VoiceTranscript.model_validate(result)
        return {"ok": True, **transcript.model_dump()}
    except ValidationError:
        return {"ok": False, "error": "invalid voice result"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


_pipeline = None
_pipecat_pipeline = None


def build_pipeline(backend: str = "whisper") -> VoiceMediaPort:
    """Select the batch media Strategy at the composition root."""
    global _pipeline, _pipecat_pipeline
    if backend == "whisper":
        if _pipeline is None:
            _pipeline = VoicePipeline(build_transcriber(), build_cleanup())
        return _pipeline
    if backend == "pipecat":
        if _pipecat_pipeline is None:
            from .pipecat_media.adapter import build_pipecat_transcriber

            _pipecat_pipeline = VoicePipeline(build_pipecat_transcriber(), build_cleanup())
        return _pipecat_pipeline
    raise ValueError(f"unsupported voice media backend: {backend}")
