"""Narrow internal port for PCM speech recognition."""

from typing import Protocol


class PcmTranscriber(Protocol):
    def transcribe_pcm(self, pcm: bytes) -> str:
        ...
