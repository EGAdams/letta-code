"""Shapes that cross the process boundary: database rows in, JSON out."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DebuggerSettings(BaseModel):
    db_path: str
    adw_names: list[str] = Field(default_factory=lambda: ['adw_debug_pilot', 'adw_interface_scala_file_scan'])
    stall_timeout_seconds: float = 120.0
    bootstrap_runs: int = 5
    page_limit: int = 1000


class RawEvent(BaseModel):
    """One row of sssf.db's events table, untouched. `cursor` is its rowid."""
    cursor: int
    event_id: str
    run_id: str
    adw_name: str = ''
    phase_id: str = ''
    type: str = ''
    name: str = ''
    payload_json: str = ''
    recorded_at: str = ''


class RunRow(BaseModel):
    run_id: str
    adw_name: str = ''
    status: str = ''
    started_at: str = ''
    ended_at: Optional[str] = None
    pid: Optional[int] = None
    process_command: str = ''
    process_ended_at: Optional[str] = None


class DebugEvent(BaseModel):
    """What the browser reads. Every identity is explicit; none is a display name."""
    cursor: int
    event_id: str
    recorded_at: str
    kind: str
    message: str = ''
    payload: dict[str, Any] = Field(default_factory=dict)
    machine: str = ''
    adw_name: str = ''
    run_id: str = ''
    phase_id: str = ''
    phase_name: str = ''
    instance_id: str = ''
    attempt: Optional[int] = None
    status: Optional[str] = None            # running | pass | fail, when the event is authoritative
    source_instance: str = ''
    target_instance: str = ''
    tool: str = ''
    call_id: str = ''
    deadline_at: Optional[str] = None


class DebugRun(BaseModel):
    run_id: str
    adw_name: str
    status: str                             # running | success | fail | interrupted
    started_at: str = ''
    ended_at: Optional[str] = None
    process_alive: Optional[bool] = None    # None = no process row to judge by


class FeedResponse(BaseModel):
    ok: bool = True
    error: str = ''
    machine: str = ''
    server_now: str = ''
    stall_timeout_seconds: float = 120.0
    adw_names: list[str] = Field(default_factory=list)
    bootstrap: bool = False
    cursor: int = 0
    runs: list[DebugRun] = Field(default_factory=list)
    events: list[DebugEvent] = Field(default_factory=list)
