"""Stream one Letta Code turn as validated NDJSON records.

The subprocess adapter owns process lifetime and converts the CLI's provider
records into one stable envelope.  HTTP concerns stay in ``http_app`` and the
browser decides which provider events are suitable for display or speech.
"""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hosts import LETTA_BASE_URL
from letta_code.runner import (
    _LETTA_CODE_FORBIDDEN_INPUT_RE,
    _LETTA_CODE_MAX_PROMPT_CHARS,
    _letta_code_command,
)
from letta_ids import _TERMINAL_ID_RE
from paths import REPO_ROOT


class ConversationStreamRequest(BaseModel):
    """Untrusted browser request for one streamed turn."""

    model_config = ConfigDict(extra="forbid")

    agent: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=_LETTA_CODE_MAX_PROMPT_CHARS)
    conversation_id: str | None = None

    @field_validator("agent")
    @classmethod
    def safe_agent_id(cls, value: str) -> str:
        if not _TERMINAL_ID_RE.fullmatch(value):
            raise ValueError("invalid Letta agent id")
        return value

    @field_validator("text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        if not value.strip():
            raise ValueError("message is empty")
        if _LETTA_CODE_FORBIDDEN_INPUT_RE.search(value):
            raise ValueError("message contains unsupported control characters")
        return value

    @field_validator("conversation_id")
    @classmethod
    def safe_conversation_id(cls, value: str | None) -> str | None:
        if value is not None and not _TERMINAL_ID_RE.fullmatch(value):
            raise ValueError("invalid Letta conversation id")
        return value


class ConversationStreamRecord(BaseModel):
    """Stable record written to the browser's NDJSON response."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["event", "error"]
    event: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def provider_event(cls, event: dict[str, Any]) -> "ConversationStreamRecord":
        return cls(type="event", event=event)

    @classmethod
    def failure(cls, error: str) -> "ConversationStreamRecord":
        return cls(type="error", error=error)


def _terminate_process_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


def _drain_stderr(pipe, chunks: list[str]) -> None:
    if pipe is None:
        return
    for chunk in iter(pipe.readline, ""):
        chunks.append(chunk)


def stream_letta_code_message(
    request: ConversationStreamRequest,
    *,
    timeout: float = 1770,
    popen=subprocess.Popen,
) -> Iterator[ConversationStreamRecord]:
    """Yield validated CLI records and always reap the complete process tree."""

    agent_id = request.agent

    command = _letta_code_command()
    runtime_path = os.path.dirname(command[0])
    child_path = os.environ.get("PATH", "")
    if runtime_path:
        child_path = runtime_path + (os.pathsep + child_path if child_path else "")
    session_args = (
        ["--conversation", request.conversation_id]
        if request.conversation_id
        else ["--agent", agent_id]
    )
    proc = popen(
        [
            *command,
            *session_args,
            "--prompt",
            request.text,
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--memfs-startup",
            "skip",
            "--permission-mode",
            "acceptEdits",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        bufsize=1,
        env={**os.environ, "PATH": child_path, "LETTA_BASE_URL": LETTA_BASE_URL},
    )
    stderr_chunks: list[str] = []
    stderr_thread = threading.Thread(
        target=_drain_stderr, args=(proc.stderr, stderr_chunks), daemon=True
    )
    stderr_thread.start()
    started = time.monotonic()
    selector = selectors.DefaultSelector()
    if proc.stdout is None:
        _terminate_process_group(proc)
        raise RuntimeError("Letta Code stream has no stdout")
    selector.register(proc.stdout, selectors.EVENT_READ)
    saw_result = False
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            ready = selector.select(min(remaining, 0.25))
            if not ready:
                if proc.poll() is not None:
                    break
                continue
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                saw_result = True
            yield ConversationStreamRecord.provider_event(event)

        returncode = proc.wait(timeout=1)
        stderr_thread.join(timeout=1)
        if returncode != 0:
            detail = "".join(stderr_chunks).strip() or "Letta Code failed"
            yield ConversationStreamRecord.failure(detail[-1000:])
        elif not saw_result:
            yield ConversationStreamRecord.failure("Letta Code stream ended without a result")
    except GeneratorExit:
        raise
    except subprocess.TimeoutExpired:
        yield ConversationStreamRecord.failure("Toyota took too long to answer")
    finally:
        selector.close()
        _terminate_process_group(proc)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
