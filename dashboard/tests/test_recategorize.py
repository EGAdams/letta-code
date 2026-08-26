"""Tests for finance/recategorize.py -- the category write and its undo.

Pointed at the owning module, never at `server`. The code under test closes
over its own module globals, so `monkeypatch.setattr(server, 'X', ...)` would
isolate nothing here while looking exactly like it did.

Everything server.py keeps is injected through `Collaborators`, so these run
with no database, no report-mount configuration and no taxonomy.
"""
import re

import pytest
from pydantic import ValidationError

import server
from finance import recategorize
from finance.recategorize import (
    Collaborators,
    RecategorizeRequest,
    ReportRowClass,
    recategorize_expense,
    undo_recategorize_expense,
    update_report_row_color,
)
from finance.report_page import ReportRowMatch

RECEIPT_ONLY = '/api/rol-finance-receipt-only-report'

_DINERS_ROW_HTML = """\
<table><tbody>
<tr class="{cls}" data-vendor-key="trinity_church" onclick="openCategoryPicker(this)">
<td>2025-01-17</td><td>-50.00</td><td>TRINITY CHURCH</td>
</tr>
</tbody></table>
"""


def _write_report(tmp_path, cls):
    p = tmp_path / 'report.html'
    p.write_text(_DINERS_ROW_HTML.format(cls=cls), encoding='utf-8')
    return p


def _write_verified_row(report_dir, vendor_key, date_str, amount_str,
                        cls='cat-uncategorized'):
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'report.html').write_text(
        f'<table><tbody>\n'
        f'<tr class="{cls}" data-vendor-key="{vendor_key}" onclick="openCategoryPicker(this)">'
        f'<td>DESC</td><td class="number">{amount_str}</td><td>{date_str}</td></tr>\n'
        f'</tbody></table>',
        encoding='utf-8',
    )


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchall(self):
        return self.rows


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.cursors = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        cur = _FakeCursor(self.rows)
        self.cursors.append(cur)
        return cur


class _DateSelectCursor:
    """Cursor that returns expense rows only when the queried date matches."""

    def __init__(self, match_date, rows_for_match):
        self._match = match_date
        self._rows = rows_for_match
        self._last_date = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, _sql, params=None):
        self._last_date = params[0] if params else None

    def fetchall(self):
        if self._last_date == self._match:
            return self._rows
        return []


class _DateSelectConnection:
    def __init__(self, match_date, rows_for_match):
        self._cursor = _DateSelectCursor(match_date, rows_for_match)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor


_CATEGORY_IDS = {
    'Food & Hospitality': (130, 'cat-food-and-hospitality'),
    'Gifts & Love Offerings': (190, 'cat-gifts-and-love-offerings'),
    'Travel & Vehicle': (210, 'cat-travel-and-vehicle'),
    'Personal': (240, 'cat-personal'),
    'Uncategorized': (None, 'cat-uncategorized'),
}
_CLASS_FOR_NAME = {name: cls for name, (_id, cls) in _CATEGORY_IDS.items()}
_NAME_FOR_ID = {i: name for name, (i, _c) in _CATEGORY_IDS.items() if i is not None}


class _FakeTaxonomy:
    def label_for(self, category_id):
        return _NAME_FOR_ID.get(category_id, 'Uncategorized')


def _deps(connection=None, *, report_file_for_url=None,
          find_matching_report_row=None, resolve=None):
    """A Collaborators bundle with nothing live behind it."""
    return Collaborators(
        get_connection=lambda: connection,
        resolve_reporting_category=resolve or (
            lambda name: _CATEGORY_IDS.get(name, (None, None))),
        css_class_for_report_name=lambda name: _CLASS_FOR_NAME.get(
            name, 'cat-uncategorized'),
        find_matching_report_row=find_matching_report_row or (
            lambda *_a, **_kw: None),
        report_file_for_url=report_file_for_url or (lambda _p: None),
        vendor_prefix=lambda id_light: re.sub(
            r'_\d{2}_\d{2}_\d{2}_\d+_\d+$', '', id_light or ''),
        category_taxonomy=_FakeTaxonomy,
        receipt_only_report_path=RECEIPT_ONLY,
    )


@pytest.fixture(autouse=True)
def _no_real_undo_journal(monkeypatch):
    """Keep every test off the real category_undo_journal.json on disk."""
    monkeypatch.setattr(recategorize, '_record_category_undo',
                        lambda action, _get_connection: 'undo-token-test')
    monkeypatch.setattr(recategorize, '_undo_category_action',
                        lambda token, _get_connection: {
                            'status': 'missing', 'error': 'not stubbed'})


# ── Repainting the <tr> on disk ──────────────────────────────────────────────
# These three catch the bugs fixed during the Diners 0587 Year session:
# a doubled cat-* when the same category was picked twice, a stale cat-* left
# behind when the category changed, and sibling rows sharing a date+amount.

def test_update_report_row_color_same_category_no_duplicate_class(tmp_path):
    """Picking the same category a second time must not produce 'cat-x cat-x'."""
    p = _write_report(tmp_path, 'cat-food-and-hospitality')

    result = update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00',
        'cat-food-and-hospitality',
        report_file_for_url=lambda _: str(p))

    assert result is True
    html = p.read_text(encoding='utf-8')
    assert 'cat-food-and-hospitality cat-food-and-hospitality' not in html
    assert 'cat-food-and-hospitality' in html


def test_update_report_row_color_replaces_stale_cat_class(tmp_path):
    """Changing category must strip the old cat-* class entirely, not append."""
    p = _write_report(tmp_path, 'cat-food-and-hospitality')

    update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00', 'cat-personal',
        report_file_for_url=lambda _: str(p))

    html = p.read_text(encoding='utf-8')
    assert 'cat-personal' in html
    assert 'cat-food-and-hospitality' not in html


def test_update_report_row_color_uses_expense_id_for_equal_sibling_amounts(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text(
        '<table><tbody>'
        '<tr class="cat-personal" data-expense-id="1503" data-vendor-key="vision">'
        '<td>Donation A</td><td>50.00</td><td>2025-01-01</td></tr>'
        '<tr class="cat-personal" data-expense-id="1504" data-vendor-key="vision">'
        '<td>Donation B</td><td>50.00</td><td>2025-01-01</td></tr>'
        '</tbody></table>',
        encoding='utf-8',
    )

    result = update_report_row_color(
        'fake/path', 'vision', '2025-01-01', '50.00',
        'cat-gifts-and-love-offerings', expense_id=1504,
        report_file_for_url=lambda _: str(p))

    assert result is True
    html = p.read_text(encoding='utf-8')
    first, second = html.split('</tr>')[:2]
    assert 'cat-personal' in first
    assert 'cat-gifts-and-love-offerings' in second


def test_update_report_row_color_adds_class_to_a_row_that_had_none(tmp_path):
    p = tmp_path / 'report.html'
    p.write_text(
        '<table><tbody><tr data-vendor-key="trinity_church">'
        '<td>2025-01-17</td><td>-50.00</td></tr></tbody></table>',
        encoding='utf-8')

    assert update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00', 'cat-personal',
        report_file_for_url=lambda _: str(p)) is True
    assert 'class="cat-personal"' in p.read_text(encoding='utf-8')


def test_update_report_row_color_leaves_the_file_alone_when_nothing_matches(tmp_path):
    p = _write_report(tmp_path, 'cat-personal')
    before = p.read_bytes()

    assert update_report_row_color(
        'fake/path', 'someone_else', '2025-01-17', '-50.00', 'cat-personal',
        report_file_for_url=lambda _: str(p)) is False
    assert p.read_bytes() == before


def test_update_report_row_color_needs_a_vendor_key_or_an_id(tmp_path):
    p = _write_report(tmp_path, 'cat-personal')

    assert update_report_row_color(
        'fake/path', '', '2025-01-17', '-50.00', 'cat-food-and-hospitality',
        report_file_for_url=lambda _: str(p)) is False


def test_update_report_row_color_returns_false_when_the_url_maps_nowhere():
    assert update_report_row_color(
        '/nope/report.html', 'trinity_church', '2025-01-17', '-50.00',
        'cat-personal', report_file_for_url=lambda _: None) is False


# ── ReportRowClass: the class that goes into the file ────────────────────────
# `_swap_cls` strips exactly `cat-[a-z0-9-]+` when it repaints a row. Nothing
# used to check the value going in against that same pattern, so a class the
# strip cannot match survived every later re-categorisation -- and one carrying
# a quote broke out of the attribute and corrupted the report file outright.

@pytest.mark.parametrize('value', [
    'cat-personal', 'cat-uncategorized', 'cat-robert-benefits-and-medical',
    'cat-1099',
])
def test_report_row_class_accepts_every_real_bucket_class(value):
    assert ReportRowClass(value=value).value == value


@pytest.mark.parametrize('value', [
    '', 'personal', 'cat-Personal', 'cat-food hospitality',
    'cat-x" onclick="alert(1)', 'cat-x\nrow',
])
def test_report_row_class_rejects_anything_the_strip_could_not_take_back_out(value):
    with pytest.raises(ValidationError):
        ReportRowClass(value=value)


def test_every_seeded_css_class_is_a_valid_report_row_class():
    """The real taxonomy must not contain a class this model would refuse."""
    from category_taxonomy_seed import LEGACY_TAXONOMY

    for node in LEGACY_TAXONOMY.all_nodes():
        if node.css_class:
            assert ReportRowClass(value=node.css_class).value == node.css_class


def test_a_malformed_class_is_refused_instead_of_written_into_the_report(tmp_path):
    """The old code spliced this straight into class="..." and returned True."""
    p = _write_report(tmp_path, 'cat-personal')
    before = p.read_bytes()

    result = update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00',
        'cat-x" onclick="alert(1)',
        report_file_for_url=lambda _: str(p))

    assert result is False
    assert p.read_bytes() == before, 'a bad class must never reach the file'


def test_a_class_with_a_space_cannot_smuggle_in_a_second_class(tmp_path):
    """'cat-a cat-b' would paint two buckets onto one row, permanently."""
    p = _write_report(tmp_path, 'cat-personal')

    assert update_report_row_color(
        'fake/path', 'trinity_church', '2025-01-17', '-50.00',
        'cat-personal cat-housing',
        report_file_for_url=lambda _: str(p)) is False
    assert 'cat-housing' not in p.read_text(encoding='utf-8')


# ── RecategorizeRequest: the browser's payload ───────────────────────────────

def test_request_takes_a_row_id_as_int_or_digit_string():
    assert RecategorizeRequest.from_call(
        '', '', '', 'Food & Hospitality', '', '', 1503)[0].expense_id == 1503
    assert RecategorizeRequest.from_call(
        '', '', '', 'Food & Hospitality', '', '', '1503')[0].expense_id == 1503
    assert RecategorizeRequest.from_call(
        '', '10.00', '', 'Food & Hospitality', '', '', None)[0].expense_id is None
    assert RecategorizeRequest.from_call(
        '', '10.00', '', 'Food & Hospitality', '', '', '')[0].expense_id is None


def test_request_keeps_expense_id_zero_rather_than_treating_it_as_absent():
    request, error = RecategorizeRequest.from_call(
        '', '', '', 'Food & Hospitality', '', '', 0)
    assert error is None
    assert request.expense_id == 0


@pytest.mark.parametrize('raw', [3.9, 3.0, True, '3.9', 'ten', '1503abc', [1503]])
def test_request_refuses_a_row_id_that_is_not_a_whole_number(raw):
    """`int(3.9)` used to write category over expense 3, and `int(True)` over 1."""
    request, error = RecategorizeRequest.from_call(
        '', '', '', 'Food & Hospitality', '', '', raw)
    assert request is None
    assert error == {'ok': False, 'error': f'Bad expense_id: {raw!r}'}


@pytest.mark.parametrize('raw,expected', [
    ('-$150.00', '150.00'), ('+$10.00', '10.00'), ('296.41', '296.41'),
    ('1,234.56', '1234.56'), ('  -50.00 ', '50.00'),
])
def test_request_normalises_the_displayed_amount_for_the_db_lookup(raw, expected):
    request, error = RecategorizeRequest.from_call(
        '2025-01-17', raw, '', 'Food & Hospitality', '', '', None)
    assert error is None
    assert str(request.amount) == expected


@pytest.mark.parametrize('raw', ['nan', 'NaN', 'inf', '-Infinity', 'snan'])
def test_request_refuses_a_non_finite_amount(raw):
    """Decimal() accepts these. `WHERE amount='NaN'` then matches nothing, and
    the caller reported that as ok:True 'Transaction not in DB'."""
    request, error = RecategorizeRequest.from_call(
        '2025-01-17', raw, '', 'Food & Hospitality', '', '', None)
    assert request is None
    assert error == {'ok': False, 'error': f'Bad amount: {raw!r}'}


@pytest.mark.parametrize('raw', ['', 'abc', '--5'])
def test_request_refuses_an_unparseable_amount(raw):
    request, error = RecategorizeRequest.from_call(
        '2025-01-17', raw, '', 'Food & Hospitality', '', '', None)
    assert request is None
    assert error == {'ok': False, 'error': f'Bad amount: {raw!r}'}


def test_request_ignores_the_amount_entirely_when_an_id_is_given():
    """With an id the row is found by id; signed_amount is display text only."""
    request, error = RecategorizeRequest.from_call(
        '', 'nan', '', 'Food & Hospitality', '', '', 555)
    assert error is None
    assert request.amount is None


def test_a_non_finite_amount_never_reaches_the_database():
    connection = _FakeConnection([])

    result = recategorize_expense(
        '2025-01-17', 'nan', 'trinity_church', 'Food & Hospitality',
        deps=_deps(connection))

    assert result == {'ok': False, 'error': "Bad amount: 'nan'"}
    assert connection.cursors == [], 'no query should have been attempted'


# ── recategorize_expense ─────────────────────────────────────────────────────

def test_recategorize_expense_rejects_an_unknown_category():
    result = recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church', 'Not A Bucket',
        deps=_deps(_FakeConnection([])))

    assert result == {'ok': False, 'error': 'Unknown category: Not A Bucket'}


def test_recategorize_expense_rejects_parent_even_with_exact_id():
    expense = {
        'id': 1502,
        'id_light': 'vision_01_01_25_100_00',
        'description': 'Vision receipt',
        'category_id': None,
        'expense_role': 'PARENT',
    }

    result = recategorize_expense(
        '', '', '', 'Gifts & Love Offerings', expense_id=1502,
        deps=_deps(_FakeConnection([expense])))

    assert result['ok'] is False
    assert 'PARENT' in result['error']


def test_recategorize_expense_bank_only_row_returns_ok_with_warning(tmp_path):
    """Rows not in the DB (annual-summary bank-only) must return ok:True + warning."""
    p = _write_report(tmp_path, 'cat-uncategorized')

    result = recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church', 'Food & Hospitality',
        report_path='/rol_finances_reports/jan-2025/diners/report.html',
        deps=_deps(_FakeConnection([]), report_file_for_url=lambda _: str(p)))

    assert result['ok'] is True
    assert result['expense_id'] is None
    assert result['file_updated'] is True
    assert 'warning' in result
    assert 'cat-food-and-hospitality' in p.read_text(encoding='utf-8')


def test_recategorize_expense_bank_only_row_skips_the_receipt_only_tab():
    """That tab is rebuilt from the DB per load; there is no file to paint."""
    result = recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church', 'Food & Hospitality',
        report_path=RECEIPT_ONLY, deps=_deps(_FakeConnection([])))

    assert result['ok'] is True
    assert result['file_updated'] is False


def test_recategorize_expense_credit_card_posting_date_offset(tmp_path):
    """It must match the DB row when dates differ by ±1-3 days."""
    expense = {
        'id': 555,
        'id_light': 'trinity_church_01_16_25_50_00',
        'description': 'TRINITY CHURCH',
        'category_id': None,
    }
    p = _write_report(tmp_path, 'cat-uncategorized')

    result = recategorize_expense(
        '2025-01-17', '-50.00', 'trinity_church', 'Food & Hospitality',
        report_path='/rol_finances_reports/jan-2025/diners/report.html',
        deps=_deps(_DateSelectConnection('2025-01-16', [expense]),
                   report_file_for_url=lambda _: str(p)))

    assert result['ok'] is True
    assert result['expense_id'] == 555


def test_recategorize_expense_reports_a_tie_it_cannot_break():
    rows = [
        {'id': 1, 'id_light': 'a_01_16_25_50_00', 'description': 'A',
         'category_id': None, 'expense_role': 'STANDALONE'},
        {'id': 2, 'id_light': 'b_01_16_25_50_00', 'description': 'B',
         'category_id': None, 'expense_role': 'STANDALONE'},
    ]

    result = recategorize_expense(
        '2025-01-16', '-50.00', 'unrelated', 'Food & Hospitality',
        deps=_deps(_FakeConnection(rows)))

    assert result['ok'] is False
    assert '2 expenses share that date/amount' in result['error']


def test_recategorize_expense_breaks_a_tie_on_the_description():
    rows = [
        {'id': 1, 'id_light': 'a_01_16_25_50_00', 'description': 'A',
         'category_id': None, 'expense_role': 'STANDALONE'},
        {'id': 2, 'id_light': 'b_01_16_25_50_00', 'description': 'B',
         'category_id': None, 'expense_role': 'STANDALONE'},
    ]

    result = recategorize_expense(
        '2025-01-16', '-50.00', 'unrelated', 'Food & Hospitality',
        description='B', deps=_deps(_FakeConnection(rows)))

    assert result['ok'] is True
    assert result['expense_id'] == 2


def test_recategorize_expense_reports_a_db_failure_rather_than_claiming_success():
    class _Exploding:
        def __enter__(self):
            raise RuntimeError('connection refused')

        def __exit__(self, *_):
            return False

    result = recategorize_expense(
        '2025-01-16', '-50.00', 'trinity_church', 'Food & Hospitality',
        deps=_deps(_Exploding()))

    assert result['ok'] is False
    assert result['error'] == 'DB error: connection refused'


def test_recategorize_expense_records_one_time_undo_action(monkeypatch):
    expense = {
        'id': 555,
        'id_light': 'trinity_church_01_16_25_50_00',
        'description': 'TRINITY CHURCH',
        'category_id': 190,
        'expense_role': 'STANDALONE',
    }
    recorded = []
    monkeypatch.setattr(
        recategorize, '_record_category_undo',
        lambda action, _get_connection: recorded.append(action) or 'undo-token-1')

    result = recategorize_expense(
        '2025-01-16', '-50.00', 'trinity_church', 'Food & Hospitality',
        expense_id=555, deps=_deps(_FakeConnection([expense])))

    assert result['undo_token'] == 'undo-token-1'
    assert recorded == [{
        'expense_id': 555,
        'previous_category_id': 190,
        'category_id': 130,
        'previous_reporting_category': 'Gifts & Love Offerings',
        'reporting_category': 'Food & Hospitality',
        'date': '2025-01-16',
        'signed_amount': '-50.00',
        'vendor_key': 'trinity_church',
        'description': 'TRINITY CHURCH',
        'report_path': '',
    }]


def test_recategorize_expense_still_succeeds_when_the_journal_write_fails(monkeypatch):
    """The category IS changed; losing the undo token must not undo that."""
    expense = {
        'id': 555, 'id_light': 'trinity_church_01_16_25_50_00',
        'description': 'TRINITY CHURCH', 'category_id': 190,
        'expense_role': 'STANDALONE',
    }

    def _boom(_action, _get_connection):
        raise OSError('journal is read-only')

    monkeypatch.setattr(recategorize, '_record_category_undo', _boom)

    result = recategorize_expense(
        '2025-01-16', '-50.00', 'trinity_church', 'Food & Hospitality',
        expense_id=555, deps=_deps(_FakeConnection([expense])))

    assert result['ok'] is True
    assert result['undo_token'] is None


def test_recategorize_expense_no_report_path_finds_and_patches_matching_report(tmp_path):
    """The core New Records ask: categorizing with no report_path must still land
    the color in the report.html the transaction actually belongs to, when found."""
    report_dir = tmp_path / 'february' / 'platinum_year'
    _write_verified_row(report_dir, 'kum_go_2608r_walker', '2025-04-03', '28.10')
    url = '/rol_finances_reports/feb-2025/platinum_year/report.html'
    found = ReportRowMatch(report_path=url, label='Platinum Year',
                           row_vendor_key='kum_go_2608r_walker')

    expense = {'id': 990, 'id_light': 'kum_go_2608r_04_03_25_28_10',
               'description': 'KUM&GO', 'category_id': None}

    result = recategorize_expense(
        '2025-04-03', '28.10', 'kum_go_2608r', 'Travel & Vehicle',
        deps=_deps(_FakeConnection([expense]),
                   report_file_for_url=lambda _p: str(report_dir / 'report.html'),
                   find_matching_report_row=lambda *_a, **_kw: found))

    assert result['ok'] is True
    assert result['file_updated'] is True
    assert result['matched_report'] == {'report_path': url, 'label': 'Platinum Year'}
    html = (report_dir / 'report.html').read_text(encoding='utf-8')
    assert 'cat-travel-and-vehicle' in html
    assert 'cat-uncategorized' not in html


def test_recategorize_expense_no_report_path_no_match_stays_db_only():
    """A record with no static report.html row anywhere (a standalone receipt) must
    still succeed, DB-only, with matched_report left None."""
    expense = {'id': 42, 'id_light': 'meijer_01_22_25_18_40',
               'description': 'MEIJER', 'category_id': None}

    result = recategorize_expense(
        '2025-01-22', '18.40', 'meijer', 'Travel & Vehicle',
        deps=_deps(_FakeConnection([expense])))

    assert result['ok'] is True
    assert result['file_updated'] is True
    assert result['matched_report'] is None


def test_recategorize_expense_line_item_row_is_painted_by_id(tmp_path):
    """Siblings share date and amount, so only the id can pick the right <tr>."""
    p = tmp_path / 'report.html'
    p.write_text(
        '<table><tbody>'
        '<tr class="cat-uncategorized" data-expense-id="1503" data-vendor-key="vision">'
        '<td>A</td><td>50.00</td><td>2025-01-01</td></tr>'
        '<tr class="cat-uncategorized" data-expense-id="1504" data-vendor-key="vision">'
        '<td>B</td><td>50.00</td><td>2025-01-01</td></tr>'
        '</tbody></table>', encoding='utf-8')
    expense = {'id': 1504, 'id_light': 'vision_01_01_25_50_00', 'description': 'B',
               'category_id': None, 'expense_role': 'LINE_ITEM'}

    result = recategorize_expense(
        '2025-01-01', '50.00', 'vision', 'Personal', expense_id=1504,
        report_path='/rol_finances_reports/jan-2025/x/report.html',
        deps=_deps(_FakeConnection([expense]), report_file_for_url=lambda _: str(p)))

    assert result['ok'] is True and result['file_updated'] is True
    first, second = p.read_text(encoding='utf-8').split('</tr>')[:2]
    assert 'cat-uncategorized' in first
    assert 'cat-personal' in second


# ── undo_recategorize_expense ────────────────────────────────────────────────

_ACTION = {
    'expense_id': 555,
    'previous_category_id': 190,
    'category_id': 130,
    'previous_reporting_category': 'Gifts & Love Offerings',
    'reporting_category': 'Food & Hospitality',
    'date': '2025-01-16',
    'signed_amount': '-50.00',
    'vendor_key': 'trinity_church',
    'description': 'TRINITY CHURCH',
    'report_path': '/report.html',
}


def test_undo_recategorize_expense_restores_prior_category_and_report(
        tmp_path, monkeypatch):
    p = _write_report(tmp_path, 'cat-food-and-hospitality')
    monkeypatch.setattr(recategorize, '_undo_category_action',
                        lambda token, _c: {'status': 'restored', 'action': _ACTION})

    result = undo_recategorize_expense(
        'undo-token-1',
        deps=_deps(report_file_for_url=lambda _: str(p)))

    assert result['ok'] is True
    assert result['expense_id'] == 555
    assert result['category_id'] == 190
    assert result['reporting_category'] == 'Gifts & Love Offerings'
    assert result['category_class'] == 'cat-gifts-and-love-offerings'
    assert result['file_updated'] is True
    assert 'cat-gifts-and-love-offerings' in p.read_text(encoding='utf-8')


def test_undo_recategorize_expense_refuses_newer_category_change(monkeypatch):
    monkeypatch.setattr(recategorize, '_undo_category_action', lambda token, _c: {
        'status': 'conflict',
        'error': 'Expense category changed again; refusing to overwrite it.',
    })

    result = undo_recategorize_expense('undo-token-1', deps=_deps())

    assert result == {
        'ok': False,
        'error': 'Expense category changed again; refusing to overwrite it.',
    }


def test_undo_recategorize_expense_reports_an_unknown_token(monkeypatch):
    monkeypatch.setattr(recategorize, '_undo_category_action', lambda token, _c: {
        'status': 'missing',
        'error': 'That undo action was not found or has expired.',
    })

    result = undo_recategorize_expense('nope', deps=_deps())

    assert result['ok'] is False
    assert 'not found' in result['error']


def test_undo_recategorize_expense_falls_back_to_an_id_less_row_match(
        tmp_path, monkeypatch):
    """Rows written before data-expense-id existed still have to repaint."""
    p = _write_report(tmp_path, 'cat-food-and-hospitality')
    monkeypatch.setattr(recategorize, '_undo_category_action',
                        lambda token, _c: {'status': 'restored', 'action': _ACTION})

    result = undo_recategorize_expense(
        'undo-token-1', deps=_deps(report_file_for_url=lambda _: str(p)))

    assert result['file_updated'] is True, 'the second, id-less attempt must run'


def test_undo_recategorize_expense_searches_when_the_action_kept_no_report_path(
        tmp_path, monkeypatch):
    report_dir = tmp_path / 'february' / 'platinum_year'
    report_dir.mkdir(parents=True)
    # The search branch matches on data-expense-id only -- unlike the
    # known-report_path branch, it has no id-less second attempt.
    (report_dir / 'report.html').write_text(
        '<table><tbody><tr class="cat-food-and-hospitality" data-expense-id="555" '
        'data-vendor-key="trinity_church"><td>2025-01-16</td><td>-50.00</td>'
        '</tr></tbody></table>', encoding='utf-8')
    action = dict(_ACTION, report_path='')
    found = ReportRowMatch(report_path='/x/report.html', label='X',
                           row_vendor_key='trinity_church')
    monkeypatch.setattr(recategorize, '_undo_category_action',
                        lambda token, _c: {'status': 'restored', 'action': action})

    result = undo_recategorize_expense('undo-token-1', deps=_deps(
        report_file_for_url=lambda _p: str(report_dir / 'report.html'),
        find_matching_report_row=lambda *_a, **_kw: found))

    assert result['file_updated'] is True
    assert 'cat-gifts-and-love-offerings' in (
        report_dir / 'report.html').read_text(encoding='utf-8')


def test_undo_recategorize_expense_on_the_receipt_only_tab_touches_no_file(monkeypatch):
    action = dict(_ACTION, report_path=RECEIPT_ONLY)
    monkeypatch.setattr(recategorize, '_undo_category_action',
                        lambda token, _c: {'status': 'restored', 'action': action})

    def _explode(*_a, **_kw):
        raise AssertionError('must not touch a report file')

    result = undo_recategorize_expense(
        'undo-token-1', deps=_deps(report_file_for_url=_explode))

    assert result['ok'] is True
    assert result['file_updated'] is True


# ── Wiring: server.py must hand over the real collaborators ──────────────────
# Injection is only honest if something checks that production injects the real
# thing. And the names below must NOT be re-exported: a re-export is a second
# binding, so a test patching `server._update_report_row_color` would isolate
# nothing while looking exactly like it had.

def test_server_wrapper_passes_the_real_collaborators():
    deps = server._recategorize_deps()

    assert deps.resolve_reporting_category is server._resolve_reporting_category
    assert deps.css_class_for_report_name is server._css_class_for_report_name
    assert deps.find_matching_report_row is server._find_matching_report_row
    assert deps.report_file_for_url is server._report_file_for_url
    assert deps.vendor_prefix is server._vendor_prefix
    assert deps.category_taxonomy is server._get_category_taxonomy
    assert deps.receipt_only_report_path == server.RECEIPT_ONLY_REPORT_PATH


def test_server_wrapper_resolves_the_connection_at_call_time(monkeypatch):
    """The bundle is built per call, so replacing the factory is honoured."""
    sentinel = object()
    monkeypatch.setattr(server, '_rol_get_connection', lambda: sentinel)

    assert server._recategorize_deps().get_connection() is sentinel


@pytest.mark.parametrize('name', [
    '_update_report_row_color', '_record_category_undo', '_undo_category_action',
    '_get_category_undo_service', 'CATEGORY_UNDO_JOURNAL',
])
def test_server_does_not_re_export_the_moved_names(name):
    assert not hasattr(server, name), (
        f'server.{name} is a dead re-export -- a second binding for a test to '
        'patch while the real one keeps running')
