"""Wire shapes for one recorded audio upload and its transcript."""

from pydantic import BaseModel, ConfigDict, Field


class AudioUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    audio_bytes: bytes = Field(min_length=1)
    filename: str = Field(
        default="audio.webm",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.(webm|ogg|mp4|m4a|wav|mp3|flac|aac)$",
    )


class VoiceTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    raw_transcript: str = Field(min_length=1)
    cleaned_text: str = Field(min_length=1)
