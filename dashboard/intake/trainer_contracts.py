"""Strict data contracts and narrow ports for conditional Trainer escalation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import Field, field_validator

from contracts import StrictModel


class TrainerLaunchRequest(StrictModel):
    scan_path: str = Field(min_length=1)
    scanner_name: str = Field(min_length=1)
    facade_result: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str = Field(min_length=1)
    dispatched_at: float

    @field_validator('scan_path', 'scanner_name', 'conversation_id')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('value must not be blank')
        return value

    @property
    def correlation_key(self) -> tuple[str, int]:
        return self.conversation_id, int(self.dispatched_at)


class IntakeCallback(StrictModel):
    conversation_id: str = Field(min_length=1)
    dispatched_at: float
    parsed: int | None = None
    stored: int | None = None
    expense_ids: tuple[int, ...] = ()
    duplicate_expense_ids: tuple[int, ...] = ()
    deposits_stored: int = 0
    status: str = ''

    @property
    def correlation_key(self) -> tuple[str, int]:
        return self.conversation_id, int(self.dispatched_at)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> IntakeCallback | None:
        conversation_id = str(payload.get('conversation_id') or '').strip()
        try:
            dispatched_at = float(payload.get('dispatched_at') or 0)
        except (TypeError, ValueError):
            return None
        if not conversation_id or dispatched_at <= 0:
            return None

        def optional_int(name: str) -> int | None:
            value = payload.get(name)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def ids(name: str) -> tuple[int, ...]:
            clean: list[int] = []
            for value in payload.get(name) or ():
                try:
                    parsed_value = int(value)
                except (TypeError, ValueError):
                    continue
                if parsed_value not in clean:
                    clean.append(parsed_value)
            return tuple(clean)

        return cls(
            conversation_id=conversation_id,
            dispatched_at=dispatched_at,
            parsed=optional_int('parsed'),
            stored=optional_int('stored'),
            expense_ids=ids('expense_ids'),
            duplicate_expense_ids=ids('duplicate_expense_ids'),
            deposits_stored=optional_int('deposits_stored') or 0,
            status=str(payload.get('status') or '').strip().lower(),
        )


class TrainerEscalationResult(StrictModel):
    matched: bool
    summon_required: bool
    summoned: bool
    reason: str = ''


class TrainerEscalationNotice(StrictModel):
    request: TrainerLaunchRequest
    reason: str = Field(min_length=1)
    summoned: bool


class ITrainerNotifier(ABC):
    @abstractmethod
    def notify(self, request: TrainerLaunchRequest) -> bool:
        """Launch one Trainer for the supplied intake."""


class ITrainerEscalationRecorder(ABC):
    @abstractmethod
    def record(self, notice: TrainerEscalationNotice) -> None:
        """Persist the outcome of an escalation attempt."""


class IDeadlineHandle(ABC):
    @abstractmethod
    def cancel(self) -> None:
        """Cancel a pending deadline callback."""


class IDeadlineScheduler(ABC):
    @abstractmethod
    def schedule(
        self, delay_seconds: float, callback: Callable[[], None]
    ) -> IDeadlineHandle:
        """Schedule one callback and return its cancellation handle."""


class ITrainerEscalationService(ABC):
    @abstractmethod
    def watch(self, request: TrainerLaunchRequest) -> bool:
        """Watch an intake without launching a Trainer during normal work."""

    @abstractmethod
    def observe(self, callback: IntakeCallback) -> TrainerEscalationResult:
        """Complete or escalate a watched intake from its callback evidence."""
