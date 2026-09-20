"""Adapt complete uploads to Pipecat STT through the existing Strategy seam."""

from ..media.models import AudioUpload
from ..transcription import TranscriptionStrategy
from .decoder import decode_recording_to_pcm
from .ports import PcmTranscriber
from .stt import PipecatWhisperSttAdapter


class PipecatWhisperTranscriber(TranscriptionStrategy):
    def __init__(self, stt: PcmTranscriber, decoder=decode_recording_to_pcm):
        self._stt = stt
        self._decoder = decoder

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        upload = AudioUpload(audio_bytes=audio_bytes, filename=filename)
        return self._stt.transcribe_pcm(self._decoder(upload))


def build_pipecat_transcriber() -> PipecatWhisperTranscriber:
    return PipecatWhisperTranscriber(PipecatWhisperSttAdapter())
