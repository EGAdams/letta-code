"""Shared, narrow ADW gateway for the browser-local Notes controls.

This module is deliberately transport-neutral.  StarTrekBridge and Toyota use
the same command envelope and gateway; the injected transport is the one
authorized on-PC browser session.  It is not a generic browser-control API.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import notes_activity

VERSION = "notes-adw.v1"
TASK_ID = re.compile(r"^t_[0-9a-f]{8,64}$")
ROLES = frozenset({"chatgpt", "toyota"})
WRITE_COMMANDS = frozenset({
    "notes.create", "notes.rename", "notes.record.start", "notes.record.stop",
    "notes.save",
})


class BrowserCommandTransport(Protocol):
    """The only browser capability exposed to the gateway.

    Implementations must target the existing Notes handlers, not DOM selectors
    supplied by a caller.  ``ack`` is a JSON-safe acknowledgement from the
    page and must say whether a user gesture/permission is still required.
    """

    def dispatch_notes_control(self, control: str, args: Mapping[str, Any]) -> Mapping[str, Any]: ...


class NotesAuthorizer(Protocol):
    def authorize(self, role: str, command: str, task_id: str) -> str: ...


class AllowlistedNotesAuthorizer:
    def authorize(self, role: str, command: str, task_id: str) -> str:
        if role not in ROLES:
            raise PermissionError("role is not allowed to use Notes")
        if command in WRITE_COMMANDS and not task_id:
            raise PermissionError("a task id is required for Notes writes")
        return role


@dataclass(frozen=True)
class NotesCommand:
    version: str
    command: str
    task_id: str
    correlation_id: str
    role: str
    args: Mapping[str, Any]
    idempotency_key: str

    @classmethod
    def parse(cls, raw: Mapping[str, Any]) -> "NotesCommand":
        values = {key: raw.get(key) for key in (
            "version", "command", "task_id", "correlation_id", "role", "args", "idempotency_key"
        )}
        if values["version"] != VERSION or not isinstance(values["command"], str):
            raise ValueError("unsupported Notes ADW command version")
        if not isinstance(values["task_id"], str) or not TASK_ID.fullmatch(values["task_id"]):
            raise ValueError("task_id must match t_<hex>")
        if not isinstance(values["correlation_id"], str) or not values["correlation_id"]:
            raise ValueError("correlation_id is required")
        if not isinstance(values["role"], str) or not isinstance(values["args"], dict):
            raise ValueError("role and args are required")
        if not isinstance(values["idempotency_key"], str) or not values["idempotency_key"]:
            raise ValueError("idempotency_key is required")
        return cls(**values)  # type: ignore[arg-type]


class NotesAdwGateway:
    """Command dispatcher shared by every authorized client."""

    def __init__(self, transport: BrowserCommandTransport,
                 authorizer: NotesAuthorizer | None = None):
        self._transport = transport
        self._authorizer = authorizer or AllowlistedNotesAuthorizer()
        self._replies: dict[str, dict[str, Any]] = {}

    def execute(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        try:
            command = NotesCommand.parse(raw)
            self._authorizer.authorize(command.role, command.command, command.task_id)
            if command.idempotency_key in self._replies:
                reply = dict(self._replies[command.idempotency_key])
                reply["duplicate"] = True
                return reply
            if command.command not in {
                "notes.open", "notes.create", "notes.rename", "notes.record.start",
                "notes.record.stop", "notes.save", "notes.status",
            }:
                raise ValueError("unknown Notes ADW command")
            control = command.command.removeprefix("notes.")
            result = dict(self._transport.dispatch_notes_control(control, command.args))
            reply = {"ok": True, "version": VERSION, "command": command.command,
                     "task_id": command.task_id, "correlation_id": command.correlation_id,
                     "role": command.role, "result": result, "duplicate": False}
            self._replies[command.idempotency_key] = reply
            notes_activity.record("adw_command", task_id=command.task_id,
                                  actor=command.role, detail=command.command)
            return reply
        except (PermissionError, ValueError, TypeError) as exc:
            task = raw.get("task_id", "") if isinstance(raw, Mapping) else ""
            notes_activity.record("adw_error", task_id=task if isinstance(task, str) else "",
                                  detail=str(exc))
            return {"ok": False, "version": VERSION, "error": str(exc)}


def json_command(raw: str, gateway: NotesAdwGateway) -> str:
    """Parse one JSON request and return a JSON-safe response."""
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("command must be a JSON object")
        return json.dumps(gateway.execute(value), separators=(",", ":"))
    except (json.JSONDecodeError, ValueError) as exc:
        return json.dumps({"ok": False, "version": VERSION, "error": str(exc)}, separators=(",", ":"))
