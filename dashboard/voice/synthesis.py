"""Text-to-speech output strategies for the dashboard.

This is the server-rewrite boundary around edge-tts: callers depend on the
strategy while the concrete adapter owns subprocess execution and file caching.
"""

import hashlib
import os
import re
import subprocess
import threading
from uuid import uuid4
from weakref import WeakValueDictionary
from abc import ABC, abstractmethod


_VOICE_NAME_RE = re.compile(r"^[A-Za-z]{2}-[A-Za-z]{2,}-[A-Za-z0-9]+$")
_CACHE_LOCKS = WeakValueDictionary()
_CACHE_LOCKS_GUARD = threading.Lock()


def _cache_lock(path: str):
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _CACHE_LOCKS[path] = lock
        return lock


class SpeechSynthesisStrategy(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> dict:
        ...


def cache_path(cache_dir: str, text: str, voice: str) -> str:
    """Return the deterministic cache path for one voice/text pair."""
    key = hashlib.sha256(f"{voice}\x00{text}".encode("utf-8")).hexdigest()
    return os.path.join(cache_dir, f"{voice}_{key[:32]}.mp3")


class EdgeTtsSynthesizer(SpeechSynthesisStrategy):
    """Adapter over the edge-tts CLI with deterministic MP3 caching."""

    def __init__(
        self,
        binary_path: str,
        default_voice: str,
        cache_dir: str,
        timeout_sec: int = 30,
        max_text_len: int = 4000,
        runner=subprocess.run,
    ):
        self.binary_path = binary_path
        self.default_voice = default_voice
        self.cache_dir = cache_dir
        self.timeout_sec = timeout_sec
        self.max_text_len = max_text_len
        self._run = runner

    def synthesize(self, text: str, voice: str | None = None) -> dict:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "empty text"}
        if len(text) > self.max_text_len:
            text = text[: self.max_text_len]
        selected_voice = voice or self.default_voice
        if not _VOICE_NAME_RE.match(selected_voice):
            return {
                "ok": False,
                "error": f"invalid voice name: {selected_voice!r}",
            }

        output_path = cache_path(self.cache_dir, text, selected_voice)
        # Synthesizer instances are created per request. Share the lock across
        # instances so concurrent sentence preparation cannot duplicate work.
        with _cache_lock(output_path):
            return self._synthesize_locked(text, selected_voice, output_path)

    def _synthesize_locked(self, text: str, selected_voice: str, output_path: str) -> dict:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"ok": True, "path": output_path, "cached": True}

        if not os.path.exists(self.binary_path):
            return {
                "ok": False,
                "error": f"edge-tts binary not found: {self.binary_path}",
            }
        os.makedirs(self.cache_dir, exist_ok=True)
        temporary_path = f"{output_path}.tmp{uuid4().hex}"
        try:
            process = self._run(
                [
                    self.binary_path,
                    "--voice",
                    selected_voice,
                    "--text",
                    text,
                    "--write-media",
                    temporary_path,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired:
            self._remove_temporary(temporary_path)
            return {
                "ok": False,
                "error": f"edge-tts timed out after {self.timeout_sec}s",
            }
        except Exception as exc:
            self._remove_temporary(temporary_path)
            return {"ok": False, "error": f"edge-tts failed to run: {exc}"}

        if (
            process.returncode != 0
            or not os.path.exists(temporary_path)
            or os.path.getsize(temporary_path) == 0
        ):
            error = (process.stderr or "").strip() or f"exit {process.returncode}"
            try:
                os.remove(temporary_path)
            except OSError:
                pass
            return {"ok": False, "error": f"edge-tts failed: {error[:300]}"}

        os.replace(temporary_path, output_path)
        return {"ok": True, "path": output_path, "cached": False}

    @staticmethod
    def _remove_temporary(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
