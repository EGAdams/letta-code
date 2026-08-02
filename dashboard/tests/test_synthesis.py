"""Server-rewrite slice for dashboard voice output.

The edge-tts process and cache live behind a synthesis strategy so server.py
only adapts HTTP to the voice service.
"""

import subprocess
import types

from voice.synthesis import EdgeTtsSynthesizer


def _service(tmp_path, **overrides):
    binary = tmp_path / "edge-tts"
    binary.write_text("#!/bin/sh\n")
    options = {
        "binary_path": str(binary),
        "default_voice": "en-GB-SoniaNeural",
        "cache_dir": str(tmp_path / "cache"),
    }
    options.update(overrides)
    return EdgeTtsSynthesizer(**options), binary


def test_sonia_is_sent_to_edge_tts_and_the_result_is_cached(tmp_path):
    calls = []

    def runner(command, **_kwargs):
        calls.append(command)
        output = command[command.index("--write-media") + 1]
        with open(output, "wb") as stream:
            stream.write(b"ID3-sonia")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    service, binary = _service(tmp_path, runner=runner)

    first = service.synthesize("Hello from Mazda")
    second = service.synthesize("Hello from Mazda")

    assert first["ok"] is True and first["cached"] is False
    assert second["ok"] is True and second["cached"] is True
    assert len(calls) == 1
    assert calls[0][0] == str(binary)
    assert calls[0][calls[0].index("--voice") + 1] == "en-GB-SoniaNeural"


def test_invalid_input_and_voice_fail_closed(tmp_path):
    service, _ = _service(tmp_path)

    assert service.synthesize("") == {"ok": False, "error": "empty text"}
    result = service.synthesize("hello", voice="$(bad)")
    assert result["ok"] is False
    assert "invalid voice" in result["error"]


def test_missing_binary_and_process_failure_are_reported(tmp_path):
    missing, _ = _service(tmp_path, binary_path=str(tmp_path / "missing"))
    assert "not found" in missing.synthesize("hello")["error"]

    def failing_runner(_command, **_kwargs):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="network down")

    failing, _ = _service(tmp_path, runner=failing_runner)
    result = failing.synthesize("hello")
    assert result["ok"] is False
    assert "network down" in result["error"]


def test_timeout_and_runner_exception_are_reported(tmp_path):
    def timeout_runner(_command, **_kwargs):
        raise subprocess.TimeoutExpired("edge-tts", 3)

    timed_out, _ = _service(tmp_path, timeout_sec=3, runner=timeout_runner)
    assert "timed out after 3s" in timed_out.synthesize("hello")["error"]

    def broken_runner(_command, **_kwargs):
        raise OSError("cannot spawn")

    broken, _ = _service(tmp_path, runner=broken_runner)
    assert "cannot spawn" in broken.synthesize("hello")["error"]
