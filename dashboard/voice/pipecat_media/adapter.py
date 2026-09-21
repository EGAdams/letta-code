"""Adapt complete uploads to Pipecat STT through the existing Strategy seam."""

from .. import config
from ..media.models import AudioUpload
from ..media.timing import LoggingSttFallbackObserver, NullSttFallbackObserver
from ..transcription import TranscriptionStrategy
from .decoder import decode_recording_to_pcm
from .ports import PcmTranscriber
from .stt import PipecatGroqSttAdapter, PipecatWhisperSttAdapter


class PipecatBatchTranscriber(TranscriptionStrategy):
    def __init__(self, stt: PcmTranscriber, decoder=decode_recording_to_pcm):
        self._stt = stt
        self._decoder = decoder

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        upload = AudioUpload(audio_bytes=audio_bytes, filename=filename)
        return self._stt.transcribe_pcm(self._decoder(upload))


class PipecatWhisperTranscriber(PipecatBatchTranscriber):
    """Compatibility name for the original batch adapter."""


class FallbackPcmTranscriber:
    """Decorator that preserves local transcription during a Groq outage."""

    def __init__(self, primary: PcmTranscriber, fallback: PcmTranscriber,
                 observer=None):
        self.primary = primary
        self.fallback = fallback
        self.observer = observer or NullSttFallbackObserver()

    def transcribe_pcm(self, pcm: bytes) -> str:
        try:
            return self.primary.transcribe_pcm(pcm)
        except Exception as exc:
            self.observer.observe(exc)
            return self.fallback.transcribe_pcm(pcm)


def build_pcm_transcriber() -> PcmTranscriber:
    """Select the configured STT Strategy and its availability fallback."""
    if config.PIPECAT_STT_PROVIDER == "local":
        return PipecatWhisperSttAdapter()
    if config.PIPECAT_STT_PROVIDER == "groq":
        return FallbackPcmTranscriber(
            PipecatGroqSttAdapter(),
            PipecatWhisperSttAdapter(),
            LoggingSttFallbackObserver(),
        )
    raise ValueError(
        f"unsupported Pipecat STT provider: {config.PIPECAT_STT_PROVIDER}"
    )


def build_pipecat_transcriber() -> PipecatBatchTranscriber:
    return PipecatBatchTranscriber(build_pcm_transcriber())
