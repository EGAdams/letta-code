"""SQLite (WAL) store of scan jobs, idempotency keys and a content-free audit trail.

One short-lived connection per call keeps it safe across the dashboard's
request threads; every write is BEGIN IMMEDIATE so the active-job check and the
insert cannot interleave with another start.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Callable, Optional

from scan_jobs.models import ACTIVE_STATUSES, TRANSITIONS, MazdaSummary, ScanRecord, rfc3339

IDEMPOTENCY_TTL_NS = 24 * 3600 * 10**9

_MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE scans (
        scan_id     TEXT PRIMARY KEY,
        scanner     TEXT NOT NULL,
        source      TEXT NOT NULL,
        created_ns  INTEGER NOT NULL,
        status      TEXT NOT NULL,
        record_json TEXT NOT NULL
    );
    CREATE INDEX scans_recent ON scans (created_ns DESC, scan_id DESC);
    CREATE TABLE idempotency (
        scope      TEXT NOT NULL,
        key        TEXT NOT NULL,
        scan_id    TEXT NOT NULL,
        created_ns INTEGER NOT NULL,
        PRIMARY KEY (scope, key)
    );
    CREATE TABLE scan_events (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT,
        at      TEXT NOT NULL,
        actor   TEXT NOT NULL,
        event   TEXT NOT NULL,
        detail  TEXT NOT NULL DEFAULT ''
    );
    """,
)


class ScannerBusy(Exception):
    def __init__(self, scan_id: str):
        super().__init__(f'scanner already has an active scan: {scan_id}')
        self.scan_id = scan_id


class InvalidTransition(Exception):
    pass


class ScanNotFound(Exception):
    pass


class SqliteScanJobRepository:
    def __init__(self, db_path: Path, clock_ns: Callable[[], int] = time.time_ns):
        self._path = Path(db_path)
        self._clock = clock_ns
        self._path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self._path.parent, 0o700)
        self._migrate()

    # -- plumbing ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
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
        os.chmod(self._path, 0o600)

    @staticmethod
    def _load(row: Optional[tuple]) -> Optional[ScanRecord]:
        return ScanRecord.model_validate_json(row[0]) if row else None

    def _now(self) -> str:
        return rfc3339(self._clock())

    # -- jobs ----------------------------------------------------------------------
    def create(self, record: ScanRecord, created_ns: int, idempotency: Optional[tuple[str, str]],
               refuse_if_active: bool) -> tuple[ScanRecord, bool]:
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                if idempotency:
                    conn.execute('DELETE FROM idempotency WHERE created_ns < ?',
                                 (created_ns - IDEMPOTENCY_TTL_NS,))
                    hit = conn.execute('SELECT s.record_json FROM idempotency i JOIN scans s USING (scan_id) '
                                       'WHERE i.scope = ? AND i.key = ?', idempotency).fetchone()
                    if hit:
                        conn.execute('COMMIT')
                        return self._load(hit), False
                if refuse_if_active:
                    marks = ','.join('?' * len(ACTIVE_STATUSES))
                    busy = conn.execute(f'SELECT scan_id FROM scans WHERE scanner = ? AND status IN ({marks}) '
                                        'ORDER BY created_ns DESC LIMIT 1',
                                        (record.scanner, *sorted(ACTIVE_STATUSES))).fetchone()
                    if busy:
                        raise ScannerBusy(busy[0])
                conn.execute('INSERT INTO scans (scan_id, scanner, source, created_ns, status, record_json) '
                             'VALUES (?, ?, ?, ?, ?, ?)',
                             (record.scan_id, record.scanner, record.source, created_ns, record.status,
                              record.model_dump_json()))
                if idempotency:
                    conn.execute('INSERT INTO idempotency (scope, key, scan_id, created_ns) VALUES (?, ?, ?, ?)',
                                 (*idempotency, record.scan_id, created_ns))
                conn.execute('COMMIT')
            except BaseException:
                conn.execute('ROLLBACK')
                raise
        return record, True

    def _rewrite(self, scan_id: str, change: Callable[[ScanRecord], ScanRecord]) -> ScanRecord:
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                current = self._load(conn.execute('SELECT record_json FROM scans WHERE scan_id = ?',
                                                  (scan_id,)).fetchone())
                if current is None:
                    raise ScanNotFound(scan_id)
                updated = change(current)
                conn.execute('UPDATE scans SET status = ?, record_json = ? WHERE scan_id = ?',
                             (updated.status, updated.model_dump_json(), scan_id))
                conn.execute('COMMIT')
            except BaseException:
                conn.execute('ROLLBACK')
                raise
        return updated

    def transition(self, scan_id: str, status: str, **changes: object) -> ScanRecord:
        def change(current: ScanRecord) -> ScanRecord:
            if status not in TRANSITIONS.get(current.status, frozenset()):
                raise InvalidTransition(f'{scan_id}: {current.status} -> {status} is not allowed')
            fields = dict(changes, status=status, updated_at=self._now())
            return ScanRecord.model_validate({**current.model_dump(), **fields})
        return self._rewrite(scan_id, change)

    def set_mazda(self, scan_id: str, summary: MazdaSummary) -> ScanRecord:
        def change(current: ScanRecord) -> ScanRecord:
            if current.status != 'captured':
                raise InvalidTransition(f'{scan_id}: only a captured scan has a Mazda outcome')
            return current.model_copy(update={'mazda': summary, 'updated_at': self._now()})
        return self._rewrite(scan_id, change)

    def idempotent_scan_id(self, scope: str, key: str) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute('SELECT scan_id FROM idempotency WHERE scope = ? AND key = ? AND created_ns >= ?',
                               (scope, key, self._clock() - IDEMPOTENCY_TTL_NS)).fetchone()
        return row[0] if row else None

    def get(self, scan_id: str) -> Optional[ScanRecord]:
        with closing(self._connect()) as conn:
            return self._load(conn.execute('SELECT record_json FROM scans WHERE scan_id = ?',
                                           (scan_id,)).fetchone())

    def list_recent(self, limit: int, cursor: Optional[str]) -> tuple[list[ScanRecord], Optional[str]]:
        limit = max(1, min(int(limit), 50))
        sql, args = 'SELECT record_json, created_ns, scan_id FROM scans', []
        if cursor:
            created_ns, scan_id = _decode_cursor(cursor)
            sql += ' WHERE (created_ns < ?) OR (created_ns = ? AND scan_id < ?)'
            args = [created_ns, created_ns, scan_id]
        sql += ' ORDER BY created_ns DESC, scan_id DESC LIMIT ?'
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, (*args, limit + 1)).fetchall()
        page = rows[:limit]
        more = len(rows) > limit and page
        return ([self._load(r) for r in page],
                _encode_cursor(page[-1][1], page[-1][2]) if more else None)

    def bridge_starts_since(self, since_ns: int, scanner: Optional[str]) -> list[int]:
        sql = "SELECT created_ns FROM scans WHERE source = 'bridge' AND created_ns >= ?"
        args: list = [since_ns]
        if scanner:
            sql += ' AND scanner = ?'
            args.append(scanner)
        with closing(self._connect()) as conn:
            return [r[0] for r in conn.execute(sql + ' ORDER BY created_ns', args)]

    def interrupt_active(self) -> int:
        """At startup nothing can still be running: our scan threads died with the process."""
        marks = ','.join('?' * len(ACTIVE_STATUSES))
        with closing(self._connect()) as conn:
            ids = [r[0] for r in conn.execute(f'SELECT scan_id FROM scans WHERE status IN ({marks})',
                                              sorted(ACTIVE_STATUSES))]
        for scan_id in ids:
            now = self._now()
            self.transition(scan_id, 'interrupted', finished_at=now, error_code='interrupted',
                            error='The dashboard restarted while this scan was in progress.')
            self.audit(scan_id, 'dashboard', 'recovered_interrupted')
        return len(ids)

    def audit(self, scan_id: Optional[str], actor: str, event: str, detail: str = '') -> None:
        with closing(self._connect()) as conn:
            conn.execute('INSERT INTO scan_events (scan_id, at, actor, event, detail) VALUES (?, ?, ?, ?, ?)',
                         (scan_id, self._now(), actor[:80], event[:60], detail[:200]))

    def audit_rows(self, scan_id: str) -> list[tuple[str, str, str]]:
        with closing(self._connect()) as conn:
            return conn.execute('SELECT actor, event, detail FROM scan_events WHERE scan_id = ? ORDER BY id',
                                (scan_id,)).fetchall()


def _encode_cursor(created_ns: int, scan_id: str) -> str:
    return base64.urlsafe_b64encode(json.dumps([created_ns, scan_id]).encode()).decode().rstrip('=')


def _decode_cursor(cursor: str) -> tuple[int, str]:
    try:
        created_ns, scan_id = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        return int(created_ns), str(scan_id)
    except Exception as exc:  # noqa: BLE001 -- any malformed cursor is the caller's 400
        raise ValueError('invalid cursor') from exc
