"""Speech-to-text (Strategy).

WhisperCppTranscriber ports lettabot's working recipe: convert the uploaded blob
to 16 kHz mono PCM with ffmpeg, then run whisper-cli for a plain-text transcript.
The subprocess runner and the filesystem existence check are injectable so the
orchestration is unit-testable without real binaries.
"""
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from . import config


class TranscriptionError(Exception):
    pass


class TranscriptionStrategy(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        ...


def build_ffmpeg_args(ffmpeg_bin, src_path, wav_path):
    # -ar 16000 -ac 1 -c:a pcm_s16le  == what whisper.cpp expects.
    return [
        ffmpeg_bin, "-y", "-i", src_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path,
    ]


def build_whisper_args(binary_path, model_path, wav_path, output_base, language,
                       threads=None, prompt=None):
    args = [
        binary_path, "-m", model_path, "-f", wav_path,
        "-l", language, "-of", output_base, "-otxt", "-nt",
    ]
    if threads:
        args += ["-t", str(threads)]
    if prompt:
        # Initial prompt biases recognition toward our vocabulary (agent names).
        args += ["--prompt", prompt]
    return args


class WhisperCppTranscriber(TranscriptionStrategy):
    def __init__(self, binary_path, model_path, ffmpeg_path,
                 language="auto", threads=None, prompt=None,
                 runner=subprocess.run, exists=os.path.exists):
        self.binary_path = binary_path
        self.model_path = model_path
        self.ffmpeg_path = ffmpeg_path
        self.language = language
        self.threads = threads
        self.prompt = prompt
        self._run = runner
        self._exists = exists

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        if not audio_bytes:
            raise TranscriptionError("no audio data")
        for label, path in (("whisper binary", self.binary_path),
                             ("whisper model", self.model_path),
                             ("ffmpeg", self.ffmpeg_path)):
            if not self._exists(path):
                raise TranscriptionError(f"{label} not found: {path}")

        ext = (filename.rsplit(".", 1)[-1] or "webm").lower()
        with tempfile.TemporaryDirectory(prefix="dash-voice-") as tmp:
            src = os.path.join(tmp, f"source.{ext}")
            wav = os.path.join(tmp, "input.wav")
            out_base = os.path.join(tmp, "transcript")
            Path(src).write_bytes(audio_bytes)

            try:
                self._run(build_ffmpeg_args(self.ffmpeg_path, src, wav),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                self._run(build_whisper_args(self.binary_path, self.model_path, wav,
                                             out_base, self.language, self.threads, self.prompt),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            except subprocess.SubprocessError as exc:
                raise TranscriptionError(f"whisper.cpp failed: {exc}") from exc

            txt_path = out_base + ".txt"
            if not os.path.exists(txt_path):
                raise TranscriptionError("whisper.cpp produced no transcript")
            text = Path(txt_path).read_text(encoding="utf-8").strip()
            if not text:
                raise TranscriptionError("whisper.cpp returned an empty transcript")
            return text


def build_transcriber() -> TranscriptionStrategy:
    return WhisperCppTranscriber(
        config.WHISPER_CPP_BIN, config.WHISPER_MODEL_PATH, config.FFMPEG_BIN,
        language=config.WHISPER_LANGUAGE, threads=config.WHISPER_THREADS,
        prompt=config.WHISPER_PROMPT,
    )
