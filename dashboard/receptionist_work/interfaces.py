"""Ports used by the work Facade; no subprocess, MySQL or browser imports."""
from typing import Protocol
from contextlib import AbstractContextManager

from .contracts import BrowserCommand, StoredEditIntent, WorkRequest, WorkResult, WorkState


class WorkflowRunner(Protocol):
    def run(self, request: WorkRequest) -> WorkResult: ...


class WorkStorage(Protocol):
    def read(self, workspace: str) -> WorkState: ...
    def claim(self, command_id: str, client_id: str) -> BrowserCommand | None: ...


class TrainingEditor(Protocol):
    def search(self, data: dict) -> dict: ...
    def categories(self) -> dict: ...
    def edit(self, data: dict) -> dict: ...


class JsonAdwRunner(Protocol):
    def invoke(self, script: str, payload: dict, arguments: list[str] | None = None) -> dict: ...


class ExpenseCatalog(Protocol):
    def options(self) -> list[dict]: ...


class EditTransaction(Protocol):
    @property
    def intent(self) -> StoredEditIntent | None: ...
    def complete(self, result: dict) -> None: ...


class EditIntentStorage(Protocol):
    def edit(self, operation_id: str) -> AbstractContextManager[EditTransaction]: ...
