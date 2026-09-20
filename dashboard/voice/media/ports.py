"""The media operation implemented by Whisper today and Pipecat later."""

from typing import Protocol, runtime_checkable

from .models import AudioUpload, VoiceTranscript


@runtime_checkable
class VoiceMediaPort(Protocol):
    def process(self, upload: AudioUpload) -> VoiceTranscript:
        ...
