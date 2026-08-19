"""The interfaces the statement-breakup path is written against.

Nothing here knows a script path, a subprocess, or an HTTP body. Every collaborator
the use cases need appears once, as an ABC, so the composition root (server.py)
decides what satisfies it and a test decides differently without touching a line
of the application code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from finance.statement_models import (
    CommandResult,
    StatementBreakupRequest,
    StatementBreakupResponse,
    StatementStoreRequest,
    StatementStoreResponse,
)


class ICommandRunner(ABC):
    """The subprocess seam -- tests inject a fake instead of running scripts."""

    @abstractmethod
    def run(self, command: Sequence[str]) -> CommandResult:
        ...


class IStatementPreflightGateway(ABC):
    """The dashboard's existing statement preflight, as an interface.

    ``run`` returns run_statement_preflight()'s mapping (or None when the
    document is not a statement kind); ``rows`` returns the per-statement
    transaction dicts the store will actually see. Keeping both behind this port
    is what lets the extractor live in finance/ without importing server.py.
    """

    @abstractmethod
    def run(self, image_path: str, metadata: Mapping[str, Any],
            engine: str) -> Mapping[str, Any] | None:
        ...

    @abstractmethod
    def rows(self, image_path: str,
             preflight: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        ...


class IStatementExtractor(ABC):
    """Reads a scanned page into transaction rows -- Mazda's split step."""

    @abstractmethod
    def extract(self, request: StatementBreakupRequest) -> StatementBreakupResponse:
        ...


class IStatementStore(ABC):
    """Stores corrected rows -- Mazda's store step, without Mazda."""

    @abstractmethod
    def store(self, request: StatementStoreRequest) -> StatementStoreResponse:
        ...


class IStatementIntakeRecorder(ABC):
    """Folds a completed store back into the intake record the page reads."""

    @abstractmethod
    def record(self, request: StatementStoreRequest,
               response: StatementStoreResponse) -> None:
        ...


class NullStatementIntakeRecorder(IStatementIntakeRecorder):
    """Null Object: compose the service in a test with no intake record at all."""

    def record(self, request: StatementStoreRequest,
               response: StatementStoreResponse) -> None:
        return None


class IStatementBreakupService(ABC):
    """The two use cases the dashboard routes call."""

    @abstractmethod
    def break_up(self, request: StatementBreakupRequest) -> StatementBreakupResponse:
        ...

    @abstractmethod
    def store(self, request: StatementStoreRequest) -> StatementStoreResponse:
        ...
