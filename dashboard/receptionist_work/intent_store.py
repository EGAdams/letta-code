"""SQLite Adapter for the edit-intent port; policy never speaks SQL."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .contracts import BrowserCommand, StoredEditIntent


class SqliteEditTransaction:
    def __init__(self, db, operation_id: str):
        self.db, self.operation_id = db, operation_id
        row = db.execute('SELECT payload,status,receipt FROM browser_commands WHERE id=?', (operation_id,)).fetchone()
        self.intent = StoredEditIntent(command=BrowserCommand.model_validate_json(row[0]), status=row[1],
                                       receipt=json.loads(row[2]) if row[2] else None) if row else None

    def complete(self, result: dict) -> None:
        self.db.execute('UPDATE browser_commands SET status=?,receipt=? WHERE id=?',
                        ('saved' if result.get('ok') else 'failed', json.dumps(result), self.operation_id))


class SqliteEditIntents:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def edit(self, operation_id: str):
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            yield SqliteEditTransaction(db, operation_id)
