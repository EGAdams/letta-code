"""finance/vendor_review.py -- the 'pick a vendor' dialog backend."""

from finance.vendor_review import (
    PendingVendorReviewRow,
    list_pending_vendor_review,
    list_vendor_keys,
    set_receipt_vendor,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConnection:
    def __init__(self, rows):
        self._cursor = _FakeCursor(rows)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeVendorLookup:
    def __init__(self, vendor_keys=None, category_id=None):
        self._vendor_keys = vendor_keys or []
        self._category_id = category_id

    def list_vendor_keys(self):
        return self._vendor_keys

    def get_category_id(self, vendor_key):
        return self._category_id


class TestPendingVendorReviewRow:
    def test_defaults(self):
        row = PendingVendorReviewRow(expense_id=1)
        assert row.expense_date == ''
        assert row.image_url is None


class TestListVendorKeys:
    def test_returns_lookup_results(self):
        keys = [{'vendor_key': 'costco', 'category_id': 130}]
        result = list_vendor_keys(lambda: _FakeVendorLookup(keys))
        assert result == {'ok': True, 'vendor_keys': keys}

    def test_reports_load_failure(self):
        def boom():
            raise RuntimeError('yaml missing')
        result = list_vendor_keys(boom)
        assert result['ok'] is False
        assert 'yaml missing' in result['error']
        assert result['vendor_keys'] == []


class TestListPendingVendorReview:
    def test_builds_image_url_when_file_exists(self):
        row = {
            'id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
            'description': "BJ's", 'receipt_url': 'bjs.jpg', 'source_file': '/x/bjs.jpg',
        }
        result = list_pending_vendor_review(
            lambda: _FakeConnection([row]),
            lambda fp: '/rol_finances_receipts/bjs.jpg',
            path_isfile=lambda fp: True,
        )
        assert result == {'ok': True, 'rows': [{
            'expense_id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
            'description': "BJ's", 'receipt_url': 'bjs.jpg',
            'image_url': '/rol_finances_receipts/bjs.jpg',
        }]}

    def test_missing_file_has_no_image_url(self):
        row = {
            'id': 321, 'expense_date': '2026-05-10', 'amount': '40.77',
            'description': "BJ's", 'receipt_url': 'bjs.jpg', 'source_file': '/x/bjs.jpg',
        }
        result = list_pending_vendor_review(
            lambda: _FakeConnection([row]), lambda fp: '/x', path_isfile=lambda fp: False)
        assert result['rows'][0]['image_url'] is None

    def test_db_error_is_reported(self):
        def boom():
            raise RuntimeError('connection refused')
        result = list_pending_vendor_review(boom, lambda fp: fp)
        assert result == {'ok': False, 'error': 'DB error: connection refused', 'rows': []}


class TestSetReceiptVendor:
    def test_resolves_category_and_updates(self):
        conn = _FakeConnection([])
        result = set_receipt_vendor(
            lambda: conn, lambda: _FakeVendorLookup(category_id=130), 321, 'costco')
        assert result == {'ok': True, 'expense_id': 321, 'category_id': 130}
        sql, params = conn._cursor.executed[0]
        assert 'UPDATE expenses' in sql
        assert params == (130, 321)

    def test_rejects_unknown_vendor_key(self):
        result = set_receipt_vendor(
            lambda: _FakeConnection([]), lambda: _FakeVendorLookup(category_id=None),
            321, 'totally_unknown')
        assert result == {'ok': False, 'error': 'Unknown vendor_key: totally_unknown'}

    def test_rejects_bad_expense_id(self):
        result = set_receipt_vendor(
            lambda: _FakeConnection([]), lambda: _FakeVendorLookup(), 'not-an-int', 'costco')
        assert result['ok'] is False
        assert 'Bad expense_id' in result['error']

    def test_requires_vendor_key(self):
        result = set_receipt_vendor(
            lambda: _FakeConnection([]), lambda: _FakeVendorLookup(), 321, '')
        assert result == {'ok': False, 'error': 'vendor_key is required'}


class TestThePatchTargetTrap:
    """server.py's list_vendor_keys/list_pending_vendor_review/set_receipt_vendor
    are composition-root wrappers that resolve server._vendor_category_lookup,
    server._rol_get_connection and server._receipt_url_for_path through lambdas
    at call time. That late binding is what lets tests in test_server.py
    monkeypatch those three names on `server` and have it actually take effect
    -- an eager `from finance.vendor_review import list_vendor_keys` re-export
    (no wrapper) would close over this module's own lookup instead.
    """

    def test_wrapper_reads_the_injected_lookup_each_call_not_a_snapshot(self):
        box = {'lookup': _FakeVendorLookup([{'vendor_key': 'a'}])}
        result = list_vendor_keys(lambda: box['lookup'])
        assert result['vendor_keys'] == [{'vendor_key': 'a'}]

        box['lookup'] = _FakeVendorLookup([{'vendor_key': 'b'}])
        result = list_vendor_keys(lambda: box['lookup'])
        assert result['vendor_keys'] == [{'vendor_key': 'b'}]
