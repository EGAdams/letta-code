"""IAdwEventRepository over sssf.db. The only module that knows it is SQLite.

Opens the file read-only (`mode=ro`) for each call, so this process can never
write to the trace, and a missing file is an error rather than a new empty
database. The cursor is the events table's rowid: SSSF only ever inserts, one
autocommitted row at a time, so rowid order is the order events were recorded.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from .models import RawEvent, RunRow

_EVENT_COLUMNS = ('e.rowid, e.event_id, e.adw_id, s.adw_name, e.phase_id, e.type, e.name,'
                  ' e.payload_json, e.started_at')


def _marks(values) -> str:
    return ','.join('?' for _ in values)


class SqliteAdwEventRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f'file:{self._db_path}?mode=ro', uri=True, timeout=2)
        conn.execute('PRAGMA busy_timeout=2000')
        return conn

    def head_cursor(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute('SELECT COALESCE(MAX(rowid), 0) FROM events').fetchone()[0]

    def recent_runs(self, adw_names: list[str], limit: int) -> list[RunRow]:
        if not adw_names:
            return []
        sql = (f'SELECT s.adw_id, s.adw_name, s.status, s.started_at, s.ended_at,'
               f' p.pid, p.command, p.ended_at FROM sessions s'
               f" LEFT JOIN processes p ON p.adw_id = s.adw_id AND p.kind = 'adw'"
               f' WHERE s.adw_name IN ({_marks(adw_names)})'
               f" AND (s.status = 'running' OR s.adw_id IN ("
               f'   SELECT adw_id FROM sessions WHERE adw_name IN ({_marks(adw_names)})'
               f'   ORDER BY started_at DESC, adw_id DESC LIMIT ?))'
               f' ORDER BY s.started_at, s.adw_id, p.id')
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, [*adw_names, *adw_names, limit]).fetchall()
        runs: dict[str, RunRow] = {}
        for row in rows:          # a joined session has several process rows; the last one wins
            runs[row[0]] = RunRow(run_id=row[0], adw_name=row[1] or '', status=row[2] or '',
                                  started_at=row[3] or '', ended_at=row[4], pid=row[5],
                                  process_command=row[6] or '', process_ended_at=row[7])
        return list(runs.values())

    def events_for_runs(self, run_ids: list[str]) -> list[RawEvent]:
        if not run_ids:
            return []
        sql = (f'SELECT {_EVENT_COLUMNS} FROM events e JOIN sessions s ON s.adw_id = e.adw_id'
               f' WHERE e.adw_id IN ({_marks(run_ids)}) ORDER BY e.rowid')
        return self._events(sql, list(run_ids))

    def events_after(self, cursor: int, adw_names: list[str], limit: int) -> list[RawEvent]:
        if not adw_names:
            return []
        sql = (f'SELECT {_EVENT_COLUMNS} FROM events e JOIN sessions s ON s.adw_id = e.adw_id'
               f' WHERE e.rowid > ? AND s.adw_name IN ({_marks(adw_names)})'
               f' ORDER BY e.rowid LIMIT ?')
        return self._events(sql, [cursor, *adw_names, limit])

    def _events(self, sql: str, params: list) -> list[RawEvent]:
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [RawEvent(cursor=r[0], event_id=r[1] or '', run_id=r[2] or '', adw_name=r[3] or '',
                         phase_id=r[4] or '', type=r[5] or '', name=r[6] or '',
                         payload_json=r[7] or '', recorded_at=r[8] or '') for r in rows]
