"""VoicePipeline — composes transcribe -> cleanup, plus the /api/voice handler."""
from .cleanup import build_cleanup
from .transcription import build_transcriber


class VoicePipeline:
    def __init__(self, transcriber, cleanup):
        self.transcriber = transcriber
        self.cleanup = cleanup

    def process(self, audio_bytes: bytes, filename: str = "audio.webm") -> dict:
        raw = self.transcriber.transcribe(audio_bytes, filename)
        try:
            cleaned = self.cleanup.clean(raw)
        except Exception:
            cleaned = raw  # belt-and-suspenders; cleanup also falls back internally
        return {"raw_transcript": raw, "cleaned_text": cleaned}


def handle_voice_upload(pipeline, audio_bytes, filename="audio.webm") -> dict:
    """Pure request handler — used by server.py's POST /api/voice. JSON-able dict."""
    if not audio_bytes:
        return {"ok": False, "error": "empty audio upload"}
    try:
        result = pipeline.process(audio_bytes, filename)
        return {"ok": True, **result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


_pipeline = None


def build_pipeline() -> VoicePipeline:
    """Factory: lazily build the real pipeline once (whisper + Letta cleanup)."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VoicePipeline(build_transcriber(), build_cleanup())
    return _pipeline
