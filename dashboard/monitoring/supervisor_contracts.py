"""Validated cross-process observations and the supervisor's read interface."""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class TaskObservation(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    attempts: int = Field(default=0, ge=0)
    queue_age: str | float | int | None = None
    queued_at: str | float | int | None = None
    last_update: str | float | int | None = None
    started_at: str | float | int | None = None


class LedgerObservation(BaseModel):
    tasks: list[TaskObservation] | None = None
    source: str = "unavailable"
    updated_at: float | None = None
    stale: bool = False
    error: str | None = None
    # Local post-office records cannot reveal tasks never claimed at the gateway.
    coverage: str = "local-post-office-only"
    coverage_complete: bool = False
    coverage_reason: str = "Gateway-only queued tasks are not visible; full queue health is unknown."


class ITaskLedgerReader(Protocol):
    def read(self, now: float) -> LedgerObservation: ...


class PublishedSupervisorState(BaseModel):
    """Dashboard view of the supervisor's cross-process state file."""
    model_config = ConfigDict(extra="ignore")
    generated_at: FiniteFloat | None = None
    heartbeat_at: FiniteFloat | None = None
    source: str | None = None
    ledger_error: str | None = None
    ok: bool | None = None
    ledger_stale: bool = False
    thresholds: dict | None = None
    alerts: list[dict] = Field(default_factory=list)
    tasks: dict[str, dict] = Field(default_factory=dict)
    worker_diagnostic: dict | None = None
    queued_count: int | None = None
    worker_lanes: list[dict] | None = None      # each installed worker lane's own health, from the independent supervisor
    models: list[dict] = Field(default_factory=list)
    coverage: str | None = None
    coverage_complete: bool = False
    coverage_reason: str | None = None
    unknown_task_ids: list[str] = Field(default_factory=list)
    gateway_watch: dict | None = None           # the gateway's own queue watch (runs off this machine)
