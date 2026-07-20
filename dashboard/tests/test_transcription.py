"""TDD: WhisperCppTranscriber (Strategy) — ports lettabot's whisper.cpp recipe.

No real audio, binary, or model is needed: the subprocess runner and the
filesystem existence check are injected so we test argument-building and
orchestration in isolation.
"""
import pytest

from voice import config
from voice.transcription import (
    TranscriptionError,
    WhisperCppTranscriber,
    build_ffmpeg_args,
    build_whisper_args,
)


def test_default_whisper_model_matches_installed_dashboard_model():
    assert config.DEFAULT_WHISPER_MODEL_PATH.endswith(
        "/whisper.cpp/models/ggml-base.en.bin"
    )


def _val_after(args, flag):
    return args[args.index(flag) + 1]


def test_ffmpeg_args_force_16k_mono_pcm():
    args = build_ffmpeg_args("/ff", "/tmp/src.webm", "/tmp/in.wav")
    assert args[0] == "/ff"
    assert _val_after(args, "-ar") == "16000"
    assert _val_after(args, "-ac") == "1"
    assert _val_after(args, "-c:a") == "pcm_s16le"
    assert "/tmp/src.webm" in args
    assert args[-1] == "/tmp/in.wav"


def test_whisper_args_request_text_output():
    args = build_whisper_args("/bin/whisper-cli", "/m/model.bin", "/tmp/in.wav", "/tmp/out", "en")
    assert args[0] == "/bin/whisper-cli"
    assert _val_after(args, "-m") == "/m/model.bin"
    assert _val_after(args, "-f") == "/tmp/in.wav"
    assert _val_after(args, "-of") == "/tmp/out"
    assert _val_after(args, "-l") == "en"
    assert "-otxt" in args


def test_whisper_args_threads_optional():
    assert "-t" not in build_whisper_args("/b", "/m", "/w", "/o", "auto")
    args = build_whisper_args("/b", "/m", "/w", "/o", "auto", threads=4)
    assert _val_after(args, "-t") == "4"


def test_whisper_args_include_initial_prompt():
    # Biasing whisper toward the real agent names so "Mazda" isn't heard as "Melissa".
    args = build_whisper_args("/b", "/m", "/w", "/o", "en", prompt="Agents: Mazda, Frita")
    assert _val_after(args, "--prompt") == "Agents: Mazda, Frita"


def test_whisper_args_omit_prompt_when_absent():
    assert "--prompt" not in build_whisper_args("/b", "/m", "/w", "/o", "en")


def test_transcribe_passes_prompt_to_whisper():
    seen = {}

    def fake_runner(cmd, **kwargs):
        if "-otxt" in cmd:
            seen["whisper_cmd"] = cmd
            base = cmd[cmd.index("-of") + 1]
            with open(base + ".txt", "w", encoding="utf-8") as fh:
                fh.write("hi Mazda")

    t = WhisperCppTranscriber(
        "/bin/whisper-cli", "/m/model.bin", "/ff",
        prompt="Agents: Mazda", runner=fake_runner, exists=lambda p: True,
    )
    t.transcribe(b"audio", "voice.webm")
    assert "--prompt" in seen["whisper_cmd"]
    assert "Agents: Mazda" in seen["whisper_cmd"]


def test_transcribe_happy_path_runs_ffmpeg_then_whisper_and_reads_text():
    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append(cmd)
        if "-otxt" in cmd:  # the whisper call — emulate it writing <out>.txt
            base = cmd[cmd.index("-of") + 1]
            with open(base + ".txt", "w", encoding="utf-8") as fh:
                fh.write("  Tell Friday about this.  \n")

    t = WhisperCppTranscriber(
        "/bin/whisper-cli", "/m/model.bin", "/ff",
        runner=fake_runner, exists=lambda p: True,
    )
    text = t.transcribe(b"\x00\x01binary-audio", "voice.webm")

    assert text == "Tell Friday about this."          # stripped
    assert any("-ar" in c for c in calls)             # ffmpeg ran
    assert any("-otxt" in c for c in calls)           # whisper ran
    assert calls[0][0] == "/ff"                       # ffmpeg first


def test_transcribe_missing_binary_raises():
    t = WhisperCppTranscriber(
        "/no/whisper", "/m/model.bin", "/ff",
        runner=lambda *a, **k: None, exists=lambda p: False,
    )
    with pytest.raises(TranscriptionError):
        t.transcribe(b"x", "voice.webm")


def test_transcribe_empty_output_raises():
    def fake_runner(cmd, **kwargs):
        if "-otxt" in cmd:
            base = cmd[cmd.index("-of") + 1]
            open(base + ".txt", "w").close()  # whisper produced an empty transcript

    t = WhisperCppTranscriber(
        "/bin/whisper-cli", "/m/model.bin", "/ff",
        runner=fake_runner, exists=lambda p: True,
    )
    with pytest.raises(TranscriptionError):
        t.transcribe(b"x", "voice.webm")
