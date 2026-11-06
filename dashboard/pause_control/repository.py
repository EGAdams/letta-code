"""SQLite (WAL) store of control requests, idempotency keys and a content-free
audit trail. Same shape as scan_jobs.repository.SqliteScanJobRepository: one
short-lived connection per call, BEGIN IMMEDIATE around every write so the
open-request check and the insert cannot interleave.

Durability note for "restart recovery": unlike a scan job, a control request
has no in-process thread that dies with the dashboard, so a restart recovers
it for free -- a new repository pointed at the same file sees the exact same
rows. Nothing here is marked "interrupted" on startup.
"""

from __future__ import annotations

import time
from contextlib import closing
from pathlib import Path
from typing import Callable, Optional

from pause_control.models import OPEN_STATUSES, TRANSITIONS, ControlAction, ControlRecord, rfc3339

try:
    import sqlite3
except ImportError:  # pragma: no cover
    sqlite3 = None  # type: ignore[assignment]

IDEMPOTENCY_TTL_NS = 24 * 3600 * 10**9

_MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE control_requests (
        request_id  TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL,
        action      TEXT NOT NULL,
        created_ns  INTEGER NOT NULL,
        status      TEXT NOT NULL,
        record_json TEXT NOT NULL
    );
    CREATE INDEX control_requests_task ON control_requests (task_id, action);
    CREATE INDEX control_requests_recent ON control_requests (created_ns DESC, request_id DESC);
    CREATE TABLE idempotency (
        scope      TEXT NOT NULL,
        key        TEXT NOT NULL,
        request_id TEXT NOT NULL,
        created_ns INTEGER NOT NULL,
        PRIMARY KEY (scope, key)
    );
    CREATE TABLE control_events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT,
        at         TEXT NOT NULL,
        actor      TEXT NOT NULL,
        event      TEXT NOT NULL,
        detail     TEXT NOT NULL DEFAULT ''
    );
    """,
)


class InvalidTransition(Exception):
    pass


class ControlRequestNotFound(Exception):
    pass


class SqliteControlLedger:
    def __init__(self, db_path: Path, clock_ns: Callable[[], int] = time.time_ns):
        self._path = Path(db_path)
        self._clock = clock_ns
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    # -- plumbing ------------------------------------------------------------------
    def _connect(self):
        conn = sqlite3.connect(str(self._path), timeout=15, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=15000')
        return conn

    def _migrate(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)')
            row = conn.execute('SELECT MAX(version) FROM schema_version').fetchone()
            current = row[0] or 0
            for version, script in enumerate(_MIGRATIONS, start=1):
                if version > current:
                    for statement in filter(str.strip, script.split(';')):
                        conn.execute(statement)
                    conn.execute('INSERT INTO schema_version (version) VALUES (?)', (version,))
            conn.execute('COMMIT')

    @staticmethod
    def _load(row: Optional[tuple]) -> Optional[ControlRecord]:
        return ControlRecord.model_validate_json(row[0]) if row else None

    def _now(self) -> str:
        return rfc3339(self._clock())

    # -- requests --------------------------------------------------------------
    def create(self, record: ControlRecord, created_ns: int,
               idempotency: Optional[tuple[str, str]]) -> tuple[ControlRecord, bool]:
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                if idempotency:
                    conn.execute('DELETE FROM idempotency WHERE created_ns < ?',
                                 (created_ns - IDEMPOTENCY_TTL_NS,))
                    hit = conn.execute(
                        'SELECT c.record_json FROM idempotency i JOIN control_requests c '
                        'USING (request_id) WHERE i.scope = ? AND i.key = ?', idempotency).fetchone()
                    if hit:
                        conn.execute('COMMIT')
                        return self._load(hit), False
                # An open pause is the same request until a resume is asked for after it: that resume supersedes
                # it, so a pause after the resume is a fresh cycle, not a replay of the first.
                existing = conn.execute(
                    "SELECT record_json FROM control_requests c WHERE task_id = ? AND action = ? "
                    "AND status = ? AND NOT (? = 'pause' AND EXISTS (SELECT 1 FROM control_requests r "
                    "WHERE r.task_id = c.task_id AND r.action = 'resume' AND r.rowid > c.rowid)) "
                    "ORDER BY created_ns DESC LIMIT 1",
                    (record.task_id, record.action, OPEN_STATUSES[record.action], record.action)).fetchone()
                if existing:
                    conn.execute('COMMIT')
                    return self._load(existing), False
                conn.execute(
                    'INSERT INTO control_requests (request_id, task_id, action, created_ns, status, '
                    'record_json) VALUES (?, ?, ?, ?, ?, ?)',
                    (record.request_id, record.task_id, record.action, created_ns, record.status,
                     record.model_dump_json()))
                if idempotency:
                    conn.execute(
                        'INSERT INTO idempotency (scope, key, request_id, created_ns) VALUES (?, ?, ?, ?)',
                        (*idempotency, record.request_id, created_ns))
                conn.execute('COMMIT')
            except BaseException:
                conn.execute('ROLLBACK')
                raise
        return record, True

    def _rewrite(self, request_id: str, change: Callable[[ControlRecord], ControlRecord]) -> ControlRecord:
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                current = self._load(conn.execute(
                    'SELECT record_json FROM control_requests WHERE request_id = ?', (request_id,)).fetchone())
                if current is None:
                    raise ControlRequestNotFound(request_id)
                updated = change(current)
                conn.execute('UPDATE control_requests SET status = ?, record_json = ? WHERE request_id = ?',
                             (updated.status, updated.model_dump_json(), request_id))
                conn.execute('COMMIT')
            except BaseException:
                conn.execute('ROLLBACK')
                raise
        return updated

    def transition(self, request_id: str, status: str, **changes: object) -> ControlRecord:
        def change(current: ControlRecord) -> ControlRecord:
            if status not in TRANSITIONS.get(current.status, frozenset()):
                raise InvalidTransition(f'{request_id}: {current.status} -> {status} is not allowed')
            fields = dict(changes, status=status, updated_at=self._now())
            return ControlRecord.model_validate({**current.model_dump(), **fields})
        return self._rewrite(request_id, change)

    def get(self, request_id: str) -> Optional[ControlRecord]:
        with closing(self._connect()) as conn:
            return self._load(conn.execute(
                'SELECT record_json FROM control_requests WHERE request_id = ?', (request_id,)).fetchone())

    def open_for_task(self, task_id: str, action: ControlAction) -> Optional[ControlRecord]:
        with closing(self._connect()) as conn:
            return self._load(conn.execute(
                "SELECT record_json FROM control_requests WHERE task_id = ? AND action = ? AND status = ? "
                "ORDER BY created_ns DESC LIMIT 1", (task_id, action, OPEN_STATUSES[action])).fetchone())

    def list_for_task(self, task_id: str) -> list[ControlRecord]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT record_json FROM control_requests WHERE task_id = ? ORDER BY created_ns',
                (task_id,)).fetchall()
        return [self._load(r) for r in rows]

    def list_recent(self, limit: int) -> list[ControlRecord]:
        limit = max(1, min(int(limit), 200))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT record_json FROM control_requests ORDER BY created_ns DESC, request_id DESC LIMIT ?',
                (limit,)).fetchall()
        return [self._load(r) for r in rows]

    def audit(self, request_id: Optional[str], actor: str, event: str, detail: str = '') -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                'INSERT INTO control_events (request_id, at, actor, event, detail) VALUES (?, ?, ?, ?, ?)',
                (request_id, self._now(), actor[:80], event[:60], detail[:200]))

    def audit_rows(self, request_id: str) -> list[tuple[str, str, str]]:
        with closing(self._connect()) as conn:
            return conn.execute(
                'SELECT actor, event, detail FROM control_events WHERE request_id = ? ORDER BY id',
                (request_id,)).fetchall()
