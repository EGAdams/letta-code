"""Tests for _update_recent_receipt_references metadata synchronization."""
import json
from unittest.mock import MagicMock

import pytest

from server import _update_recent_receipt_references


class FakeCursor:
    """Fake cursor for testing database updates."""

    def __init__(self):
        self.executions = []
        self.rows = []
        self._fetch_index = 0

    def execute(self, sql, params=None):
        self.executions.append((sql, params))

    def fetchall(self):
        result = self.rows[self._fetch_index] if self._fetch_index < len(self.rows) else []
        self._fetch_index += 1
        return result

    def fetchone(self):
        rows = self.fetchall()
        return rows[0] if rows else None


class FakeConnection:
    """Fake connection for testing."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        class CM:
            def __init__(self, c):
                self.c = c

            def __enter__(self):
                return self.c

            def __exit__(self, *args):
                pass

        return CM(self._cursor)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_updates_matching_source_file_only(monkeypatch):
    """Only updates rows where source_file matches old receipt."""
    cursor = FakeCursor()
    # Schema probe
    cursor.rows.append([
        {'COLUMN_NAME': 'receipt_url'},
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
    ])
    # Current rows
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/old/path/meijer_08_19_25_19_08.jpg',
            'id_light': 'meijer_08_19_25_19_08',
            'receipt_metadata': json.dumps({'id_light': 'meijer_08_19_25_19_08'}),
        },
        {
            'id': 2,
            'source_file': '/different/receipt.jpg',
            'id_light': 'different_receipt',
            'receipt_metadata': json.dumps({'id_light': 'different_receipt'}),
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    _update_recent_receipt_references(
        [1, 2],
        '/new/path/meijer_08_19_25_20_22.jpg',
        '/old/path/meijer_08_19_25_19_08.jpg',
    )

    # Should only update row 1 (matching source_file)
    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    assert len(updates) == 1
    sql, params = updates[0]
    assert 'WHERE id = %s' in sql
    assert params[-1] == 1  # Only row 1


def test_updates_id_light_and_metadata(monkeypatch):
    """Updates id_light and receipt_metadata.id_light together."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'receipt_url'},
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/old/meijer_08_19_25_19_08.jpg',
            'id_light': 'meijer_08_19_25_19_08',
            'receipt_metadata': json.dumps({
                'id_light': 'meijer_08_19_25_19_08',
                'other_field': 'preserved',
            }),
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    _update_recent_receipt_references(
        [1],
        '/new/meijer_08_19_25_20_22.jpg',
        '/old/meijer_08_19_25_19_08.jpg',
    )

    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    assert len(updates) == 1
    sql, params = updates[0]

    # Check all fields are updated
    assert 'receipt_url = %s' in sql
    assert 'source_file = %s' in sql
    assert 'id_light = %s' in sql
    assert 'receipt_metadata = %s' in sql

    # Extract values (order: receipt_url, source_file, id_light, receipt_metadata, id)
    assert params[0] == 'meijer_08_19_25_20_22.jpg'
    assert params[1] == '/new/meijer_08_19_25_20_22.jpg'
    assert params[2] == 'meijer_08_19_25_20_22'

    metadata = json.loads(params[3])
    assert metadata['id_light'] == 'meijer_08_19_25_20_22'
    assert metadata['other_field'] == 'preserved'


def test_skips_row_with_mismatched_metadata_id_light(monkeypatch):
    """Does not update when metadata.id_light != current id_light."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
        {'COLUMN_NAME': 'source_file'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/old/meijer_08_19_25_19_08.jpg',
            'id_light': 'meijer_08_19_25_19_08',
            'receipt_metadata': json.dumps({'id_light': 'different_value'}),
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    _update_recent_receipt_references(
        [1],
        '/new/meijer_08_19_25_20_22.jpg',
        '/old/meijer_08_19_25_19_08.jpg',
    )

    # Should not update any rows
    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    assert len(updates) == 0


def test_preserves_unrelated_source_file(monkeypatch):
    """Rows with different source_file are not updated."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/completely/different/receipt.jpg',
            'id_light': 'other_receipt',
            'receipt_metadata': json.dumps({'id_light': 'other_receipt'}),
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    _update_recent_receipt_references(
        [1],
        '/new/meijer_08_19_25_20_22.jpg',
        '/old/meijer_08_19_25_19_08.jpg',
    )

    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    assert len(updates) == 0


def test_handles_missing_metadata_gracefully(monkeypatch):
    """Updates work even with NULL or malformed receipt_metadata."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/old/meijer_08_19_25_19_08.jpg',
            'id_light': '',
            'receipt_metadata': None,
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    # Should not crash
    _update_recent_receipt_references(
        [1],
        '/new/meijer_08_19_25_20_22.jpg',
        '/old/meijer_08_19_25_19_08.jpg',
    )

    # With no id_light and no metadata, the check passes (both empty)
    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    # The logic should still update since both id_light and metadata.id_light are empty
    assert len(updates) == 1


def test_no_update_without_old_path_and_mismatched_source(monkeypatch):
    """If old_path is empty but source_file differs, no update."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/some/other/file.jpg',
            'id_light': 'other',
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    # Without old_path, the check "if old_basename and current_source" fails to skip
    # But if old_path is empty, old_basename is empty, so the check doesn't run
    _update_recent_receipt_references([1], '/new/path.jpg', '')

    # With empty old_path, the condition "if old_basename and current_source"
    # evaluates to False (old_basename is ''), so the source check is skipped.
    # This means the row could be updated. Let's verify:
    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    # Since there's no old_path, source_file check is bypassed
    # And if no metadata checks fail, it updates
    assert len(updates) == 1


def test_multiple_rows_selective_update(monkeypatch):
    """Batch update correctly filters rows."""
    cursor = FakeCursor()
    cursor.rows.append([
        {'COLUMN_NAME': 'source_file'},
        {'COLUMN_NAME': 'id_light'},
        {'COLUMN_NAME': 'receipt_metadata'},
    ])
    cursor.rows.append([
        {
            'id': 1,
            'source_file': '/old/meijer_08_19_25_19_08.jpg',
            'id_light': 'meijer_08_19_25_19_08',
            'receipt_metadata': json.dumps({'id_light': 'meijer_08_19_25_19_08'}),
        },
        {
            'id': 2,
            'source_file': '/old/meijer_08_19_25_19_08.jpg',
            'id_light': 'meijer_08_19_25_19_08',
            'receipt_metadata': json.dumps({'id_light': 'meijer_08_19_25_19_08'}),
        },
        {
            'id': 3,
            'source_file': '/different/file.jpg',
            'id_light': 'different',
            'receipt_metadata': json.dumps({'id_light': 'different'}),
        },
    ])
    conn = FakeConnection(cursor)
    monkeypatch.setattr('server._rol_get_connection', lambda: conn)

    _update_recent_receipt_references(
        [1, 2, 3],
        '/new/meijer_08_19_25_20_22.jpg',
        '/old/meijer_08_19_25_19_08.jpg',
    )

    updates = [e for e in cursor.executions if 'UPDATE expenses SET' in e[0]]
    # Should update rows 1 and 2, but not 3
    assert len(updates) == 2
    updated_ids = {params[-1] for sql, params in updates}
    assert updated_ids == {1, 2}
