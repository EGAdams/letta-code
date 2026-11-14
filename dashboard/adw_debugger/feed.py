"""GET /api/adw-debugger/feed -- catch-up, then live delivery, on one cursor.

No `after`: the recent runs of the monitored ADWs with all their events, enough
to rebuild the diagram. `after=<cursor>`: only events recorded since. Either
way the response carries the cursor to send next. Every monitored event with a
rowid at or below that cursor has been delivered, so a reconnect that resends
its last cursor loses nothing; the browser drops any event it has seen before.

`AdwDebuggerFeed` depends on the three interfaces in ports.py and names no
implementation. `payload()` at the bottom is the composition root the route calls.
"""
from __future__ import annotations

import socket
from datetime import datetime, timezone

from .event_adapter import adapt
from .models import DebugRun, FeedResponse, RunRow
from .ports import IAdwEventRepository, IProcessProbe, ISettingsSource
from .process_probe import ProcProcessProbe
from .settings import FileAndEnvSettings
from .sqlite_repository import SqliteAdwEventRepository


class AdwDebuggerFeed:
    def __init__(self,
                 settings: ISettingsSource,
                 repository_for,                 # (db_path) -> IAdwEventRepository
                 processes: IProcessProbe,
                 machine: str):
        self._settings = settings
        self._repository_for = repository_for
        self._processes = processes
        self._machine = machine

    def read(self, after: int | None) -> FeedResponse:
        settings = self._settings.load()
        response = FeedResponse(machine=self._machine, adw_names=settings.adw_names,
                                stall_timeout_seconds=settings.stall_timeout_seconds,
                                server_now=datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                                bootstrap=after is None, cursor=after or 0)
        try:
            repository: IAdwEventRepository = self._repository_for(settings.db_path)
            head = repository.head_cursor()      # read first: later rows are simply delivered next time
            runs = repository.recent_runs(settings.adw_names, settings.bootstrap_runs)
            if after is None:
                raw = repository.events_for_runs([run.run_id for run in runs])
                full_page = False
            else:
                raw = repository.events_after(after, settings.adw_names, settings.page_limit)
                full_page = len(raw) >= settings.page_limit
        except Exception as error:               # noqa: BLE001 -- a broken trace db must not break the page
            response.ok, response.error = False, f'{type(error).__name__}: {error}'
            return response
        last = raw[-1].cursor if raw else 0
        response.cursor = last if full_page else max(head, last, after or 0)
        response.runs = [self._run(run) for run in runs]
        response.events = [adapt(event, self._machine) for event in raw]
        return response

    def _run(self, run: RunRow) -> DebugRun:
        alive = None
        if run.pid is not None:
            alive = run.process_ended_at is None and self._processes.alive(run.pid, run.process_command)
        status = run.status
        if status == 'running' and alive is False:
            status = 'interrupted'               # the process is gone and never recorded an outcome
        return DebugRun(run_id=run.run_id, adw_name=run.adw_name, status=status,
                        started_at=run.started_at, ended_at=run.ended_at, process_alive=alive)


def _after(query: dict) -> int | None:
    try:
        return max(0, int(query.get('after', [''])[0]))
    except (TypeError, ValueError, IndexError):
        return None


def payload(query: dict) -> dict:
    feed = AdwDebuggerFeed(settings=FileAndEnvSettings(),
                           repository_for=SqliteAdwEventRepository,
                           processes=ProcProcessProbe(),
                           machine=socket.gethostname())
    return feed.read(_after(query)).model_dump()
