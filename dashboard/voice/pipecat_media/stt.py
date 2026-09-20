"""Translate Pipecat's segmented Whisper frames into one batch transcript."""

import asyncio
from threading import Lock

from .. import config


def build_whisper_service():
    """Load the optional SDK and model only when the Pipecat backend is used."""
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.transcriptions.language import Language

    return WhisperSTTService(
        device="cpu",
        compute_type="int8",
        settings=WhisperSTTService.Settings(
            model=config.PIPECAT_WHISPER_MODEL,
            language=Language.EN,
            initial_prompt=config.WHISPER_PROMPT,
        ),
    )


class PipecatWhisperSttAdapter:
    """Run one complete PCM segment through Pipecat's Whisper service."""

    def __init__(self, service_factory=build_whisper_service,
                 *, transcript_type=None, error_type=None):
        self._service_factory = service_factory
        self._transcript_type = transcript_type
        self._error_type = error_type
        self._service = None
        # The dashboard HTTP server is threaded; a single model is shared safely.
        self._lock = Lock()

    def transcribe_pcm(self, pcm: bytes) -> str:
        if not pcm or len(pcm) % 2:
            raise ValueError("invalid PCM audio")
        with self._lock:
            if self._service is None:
                self._service = self._service_factory()
            transcript_type = self._transcript_type
            error_type = self._error_type
            if transcript_type is None or error_type is None:
                from pipecat.frames.frames import ErrorFrame, TranscriptionFrame

                transcript_type = transcript_type or TranscriptionFrame
                error_type = error_type or ErrorFrame

            async def collect() -> str:
                chunks = []
                async for frame in self._service.run_stt(pcm):
                    if isinstance(frame, error_type):
                        raise RuntimeError(str(frame.error))
                    if isinstance(frame, transcript_type):
                        if not isinstance(frame.text, str):
                            raise ValueError("invalid transcript text")
                        chunks.append(frame.text.strip())
                text = " ".join(chunk for chunk in chunks if chunk).strip()
                if not text:
                    raise ValueError("empty transcript")
                return text

            return asyncio.run(collect())
