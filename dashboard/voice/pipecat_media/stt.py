"""Translate Pipecat STT frames into one validated batch transcript."""

import asyncio
import io
from threading import Lock
import wave

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


def build_groq_service():
    """Build Pipecat's hosted Whisper service from dashboard configuration."""
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for the Groq STT provider")

    from pipecat.services.groq.stt import GroqSTTService
    from pipecat.transcriptions.language import Language

    return GroqSTTService(
        api_key=config.GROQ_API_KEY,
        settings=GroqSTTService.Settings(
            model=config.PIPECAT_GROQ_MODEL,
            language=Language.EN,
            prompt=config.WHISPER_PROMPT,
            temperature=0.0,
        ),
    )


def encode_pcm_as_wav(pcm: bytes) -> bytes:
    """Wrap signed 16-bit, 16 kHz mono PCM for hosted transcription APIs."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm)
    return output.getvalue()


async def close_hosted_client(service) -> None:
    """Release the per-request async HTTP client on its owning event loop."""
    client = getattr(service, "_client", None)
    close = getattr(client, "close", None)
    if close is not None:
        await close()


class PipecatSttAdapter:
    """Collect one complete Pipecat STT frame stream behind the PCM port."""

    def __init__(self, service_factory=build_whisper_service,
                 *, transcript_type=None, error_type=None,
                 audio_encoder=lambda pcm: pcm, cache_service=True,
                 service_disposer=None):
        self._service_factory = service_factory
        self._transcript_type = transcript_type
        self._error_type = error_type
        self._audio_encoder = audio_encoder
        self._cache_service = cache_service
        self._service_disposer = service_disposer
        self._service = None
        # The dashboard HTTP server is threaded. Local model inference is shared
        # safely, and hosted calls are kept deterministic at this batch boundary.
        self._lock = Lock()

    def transcribe_pcm(self, pcm: bytes) -> str:
        if not pcm or len(pcm) % 2:
            raise ValueError("invalid PCM audio")
        with self._lock:
            if self._cache_service and self._service is None:
                self._service = self._service_factory()
            transcript_type = self._transcript_type
            error_type = self._error_type
            if transcript_type is None or error_type is None:
                from pipecat.frames.frames import ErrorFrame, TranscriptionFrame

                transcript_type = transcript_type or TranscriptionFrame
                error_type = error_type or ErrorFrame

            async def collect() -> str:
                service = self._service or self._service_factory()
                try:
                    chunks = []
                    async for frame in service.run_stt(self._audio_encoder(pcm)):
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
                finally:
                    if self._service_disposer is not None:
                        await self._service_disposer(service)

            return asyncio.run(collect())


class PipecatWhisperSttAdapter(PipecatSttAdapter):
    """Run PCM through Pipecat's reusable local Faster Whisper model."""


class PipecatGroqSttAdapter(PipecatSttAdapter):
    """Run WAV-wrapped PCM through Pipecat's Groq Whisper service."""

    def __init__(self, service_factory=build_groq_service,
                 *, transcript_type=None, error_type=None):
        super().__init__(
            service_factory,
            transcript_type=transcript_type,
            error_type=error_type,
            audio_encoder=encode_pcm_as_wav,
            cache_service=False,
            service_disposer=close_hosted_client,
        )
