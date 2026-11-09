"""Contracts for read-only systemd service monitoring."""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Status = Literal['up', 'down', 'concern', 'unknown']


class ServiceHistoryEvent(BaseModel):
    at: float = Field(ge=0, allow_inf_nan=False)
    status: Status
    active: str
    detail: str
    outage_seconds: int | None = Field(default=None, ge=0)


class ServiceHistoryEntry(BaseModel):
    status: Status
    active: str
    down_since: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    events: list[ServiceHistoryEvent]


class ServiceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    key: str
    label: str
    unit: str = Field(pattern=r'^[A-Za-z0-9_@.][A-Za-z0-9_.@-]*\.service$')
    scope: Literal['user', 'system'] = 'user'


class ServiceObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    key: str
    label: str
    unit: str
    scope: Literal['user', 'system']
    status: Status = 'unknown'
    active: str = 'unknown'
    sub: str = ''
    loaded: str = ''
    enabled: str = 'unknown'
    pid: int = 0
    restarts: int = 0
    result: str = ''
    since: float | None = None
    down_since: float | None = None
    down_for_seconds: int | None = None
    detail: str = ''
    checked_at: float
    events: list[dict] = Field(default_factory=list)


class ServicePage(BaseModel):
    model_config = ConfigDict(extra='forbid')

    services: list[ServiceObservation]
    status: Status
    checked_at: float
    configuration_error: str = ''
    history_error: str = ''


class IServiceProbe(Protocol):
    def observe(self, service: ServiceDefinition, now: float) -> ServiceObservation: ...


class IServiceHistory(Protocol):
    def record(self, observations: list[ServiceObservation]) -> str: ...
