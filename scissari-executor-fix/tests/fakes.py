"""Test doubles for the red/green cycle."""
from __future__ import annotations

from typing import Optional, Sequence

from scissari_executor.interfaces import IExecutorClient, IAlertSink, IConversationSnapshotStore
from scissari_executor.models import (
    ExecutorCommand,
    ExecutorResponse,
    ExecutorFailure,
    ExecutorFailureError,
    StallReport,
)


class FakeExecutorClient(IExecutorClient):
    """Always succeeds, or always fails with a configured transport/HTTP signature."""

    def __init__(
        self,
        always_fail: Optional[str] = None,
        fail_status: Optional[int] = None,
        fail_detail: str = "",
    ):
        self.always_fail = always_fail
        self.fail_status = fail_status
        self.fail_detail = fail_detail
        self.calls: list[ExecutorCommand] = []

    async def run(self, cmd: ExecutorCommand) -> ExecutorResponse:
        self.calls.append(cmd)
        if self.always_fail or self.fail_status or self.fail_detail:
            raise ExecutorFailureError(
                ExecutorFailure(
                    status=self.fail_status,
                    transport_error=self.always_fail,
                    detail=self.fail_detail,
                )
            )
        return ExecutorResponse(ok=True, status=200, stdout="ok")


class ScriptedExecutorClient(IExecutorClient):
    """Fails the first `fail_times` calls with the given signature, then succeeds."""

    def __init__(
        self,
        fail_times: int,
        transport_error: Optional[str] = None,
        status: Optional[int] = None,
        detail: str = "",
    ):
        self.fail_times = fail_times
        self.transport_error = transport_error
        self.status = status
        self.detail = detail
        self.calls: list[ExecutorCommand] = []

    async def run(self, cmd: ExecutorCommand) -> ExecutorResponse:
        self.calls.append(cmd)
        if len(self.calls) <= self.fail_times:
            raise ExecutorFailureError(
                ExecutorFailure(
                    status=self.status,
                    transport_error=self.transport_error,
                    detail=self.detail,
                )
            )
        return ExecutorResponse(ok=True, status=200, stdout="recovered")


class FakeAlertSink(IAlertSink):
    def __init__(self) -> None:
        self.reports: list[StallReport] = []

    @property
    def last(self) -> Optional[StallReport]:
        return self.reports[-1] if self.reports else None

    async def emit(self, report: StallReport) -> None:
        self.reports.append(report)


class FakeSnapshotStore(IConversationSnapshotStore):
    def __init__(self) -> None:
        self._store: dict[str, Sequence[dict]] = {}
        self._n = 0

    def capture(self, agent_id: str, transcript: Sequence[dict]) -> str:
        self._n += 1
        sid = f"snap-{self._n}"
        self._store[sid] = list(transcript)
        return sid

    def restore(self, snapshot_id: str) -> Sequence[dict]:
        return self._store[snapshot_id]


# --- session layer (F7) fakes ---
from scissari_executor.session.interfaces import ISubprocessTransport
from scissari_executor.session.models import TransportInfo


class FakeSubprocessTransport(ISubprocessTransport):
    """Models the SDK SubprocessTransport: starts dead (pid=undefined) unless
    `alive=True`; spawn() gives it a pid.

    - spawn_fails: spawn() returns but leaves the subprocess dead (host can't start it)
    - spawn_raises: spawn() itself throws
    """

    def __init__(
        self,
        alive: bool = False,
        spawn_fails: bool = False,
        spawn_raises: bool = False,
    ):
        self._pid: Optional[int] = 4242 if alive else None
        self._closed = not alive
        self.spawn_fails = spawn_fails
        self.spawn_raises = spawn_raises
        self.spawn_calls = 0
        self.sent: list[str] = []

    @property
    def info(self) -> TransportInfo:
        return TransportInfo(pid=self._pid, closed=self._closed)

    def spawn(self) -> None:
        self.spawn_calls += 1
        if self.spawn_raises:
            raise RuntimeError("spawn boom")
        if self.spawn_fails:
            self._pid = None
            self._closed = True
            return
        self._pid = 4242
        self._closed = False

    def send(self, data: str) -> None:
        if self._pid is None or self._closed:
            raise RuntimeError("Transport not connected")  # mirrors the SDK
        self.sent.append(data)

    def close(self) -> None:
        self._closed = True
        self._pid = None
