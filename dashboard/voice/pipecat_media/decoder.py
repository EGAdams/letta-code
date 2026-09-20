"""Decode a complete browser recording to the PCM expected by Pipecat Whisper."""

import subprocess
import tempfile
from pathlib import Path

from .. import config
from ..media.models import AudioUpload


def decode_recording_to_pcm(
    upload: AudioUpload, *, ffmpeg_path: str | None = None, runner=subprocess.run
) -> bytes:
    """Return signed 16-bit, 16 kHz, mono PCM from a validated upload."""
    binary = ffmpeg_path or config.FFMPEG_BIN
    suffix = "." + upload.filename.rsplit(".", 1)[1]
    with tempfile.TemporaryDirectory(prefix="dash-pipecat-") as temporary:
        source = Path(temporary) / f"recording{suffix}"
        source.write_bytes(upload.audio_bytes)
        try:
            result = runner(
                [
                    binary, "-nostdin", "-v", "error", "-i", str(source),
                    "-ar", "16000", "-ac", "1", "-f", "s16le",
                    "-acodec", "pcm_s16le", "pipe:1",
                ],
                capture_output=True,
                check=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("audio decode failed") from exc
    pcm = result.stdout
    if not pcm or len(pcm) % 2:
        raise ValueError("audio decode produced no valid PCM")
    return pcm
