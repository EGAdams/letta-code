"""The ROL Finance month tabs and statement report cards, typed.

Round 13 of the server.py refactor (Registry). `server.py` carried the four
months as **two parallel dicts** keyed alike — `ROL_FINANCES_REPORTS_MONTHS`
(key → folder) and `ROL_FINANCES_MONTH_RANGES` (key → calendar range) — with
nothing checking they agreed. A month in one and not the other is a tab whose
status query silently returns nothing: the tab renders, the reports list, and
`/api/rol-finance-month-status` finds no recently-scanned expense because the
range lookup missed. Nothing anywhere says so.

`ReportMonth` makes that unexpressible, and goes further: the calendar range has
to *match the key*. `'feb-2025'` paired with a range ending 2025-02-29 — a date
that does not exist — used to be perfectly writable.

One destination, one definition
-------------------------------
The month list has three copies in this repo and the scanner list two, across
two languages: `RolFinanceReportsController`'s constructor hardcodes the four
month keys, the two scanner keys and the Mazda agent id as *default arguments*.
This module makes the Python side one typed collection so the JS side can take
its list from an endpoint instead of guessing. That JS change is deliberately
not in this commit (plan rule 15) — `MONTH_KEYS` below is what it should read.
"""

from __future__ import annotations

import calendar
import datetime as _dt

from pydantic import field_validator, model_validator

from contracts import StrictModel

_MONTH_ABBREVIATIONS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class ReportMonth(StrictModel):
    """One month tab: its key, its folder on disk, and the dates it covers.

    All four fields required. `start` and `end` used to live in a second dict,
    so "this month has no range" was a writable state — and the only symptom
    was a month-status query that quietly answered nothing.

    Statements straddle month boundaries, but the tabs group by the calendar
    month they are filed under, so the range is keyed off that month.
    """

    key: str
    folder: str
    start: str
    end: str

    @field_validator('key')
    @classmethod
    def _is_a_month_key(cls, value: str) -> str:
        abbrev, _, year = value.partition('-')
        if abbrev not in _MONTH_ABBREVIATIONS or not year.isdigit():
            raise ValueError(f'{value!r} is not a <mon>-<yyyy> month key')
        return value

    @field_validator('folder')
    @classmethod
    def _is_a_bare_folder(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        if '/' in value or value in ('.', '..'):
            raise ValueError(
                f'{value!r} must be a bare folder name — it is joined to '
                'ROL_FINANCES_REPORTS_PARENT to find the month on disk')
        return value

    @field_validator('start', 'end')
    @classmethod
    def _is_a_real_date(cls, value: str) -> str:
        try:
            _dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f'{value!r} is not a real date: {exc}') from exc
        return value

    @model_validator(mode='after')
    def _the_range_is_the_month_the_key_names(self) -> ReportMonth:
        abbrev, _, year = self.key.partition('-')
        month, year_n = _MONTH_ABBREVIATIONS[abbrev], int(year)
        start, end = _dt.date.fromisoformat(self.start), _dt.date.fromisoformat(self.end)
        expected_start = _dt.date(year_n, month, 1)
        expected_end = _dt.date(
            year_n, month, calendar.monthrange(year_n, month)[1])
        if start != expected_start or end != expected_end:
            raise ValueError(
                f'{self.key!r} covers {self.start}..{self.end} but that month '
                f'runs {expected_start}..{expected_end} — the month-status '
                'query would look at the wrong days and answer nothing')
        return self


class FinanceReportSpec(StrictModel):
    """One statement report card on a month tab.

    `all_year` defaults off: a card is a single month's statement unless it says
    otherwise. All-year cards are shown only under the default (January) tab,
    which is the dashboard's all-year view.
    """

    key: str
    label: str
    dir: str
    all_year: bool = False

    @field_validator('key', 'label')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('dir')
    @classmethod
    def _is_a_bare_folder(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be blank')
        if '/' in value or value.startswith('.'):
            raise ValueError(
                f'{value!r} must be a bare folder name — it is joined to the '
                "month's base dir to find report.html, and a path would let a "
                'report URL address a directory outside the reports tree')
        return value

    def as_config(self) -> dict:
        """The legacy dict, carrying `all_year` only when it is set."""
        cfg = {'key': self.key, 'label': self.label, 'dir': self.dir}
        if self.all_year:
            cfg['all_year'] = True
        return cfg


# `check_images/` is intentionally excluded — still waiting on those files.
# Reports are grouped by month (the frontend's month tabs); each monthly `dir` is
# looked up under that month's own subfolder, so a document is "ready" for a
# given month independently of the others. All-year documents are intentionally
# shown only in January, which is the dashboard's special all-year view.
REPORT_MONTHS: tuple[ReportMonth, ...] = (
    ReportMonth(key='jan-2025', folder='january',
                start='2025-01-01', end='2025-01-31'),
    ReportMonth(key='feb-2025', folder='february',
                start='2025-02-01', end='2025-02-28'),
    ReportMonth(key='mar-2025', folder='march',
                start='2025-03-01', end='2025-03-31'),
    ReportMonth(key='apr-2025', folder='april',
                start='2025-04-01', end='2025-04-30'),
)

DEFAULT_MONTH_KEY = 'jan-2025'

FINANCE_REPORT_SPECS: tuple[FinanceReportSpec, ...] = (
    FinanceReportSpec(key='fnbo-4851', label='FNBO 4851',
                      dir='january_fnbo_2025_account_4851'),
    FinanceReportSpec(key='amex-personal-year', label='Amex 1006',
                      dir='amex_personal_whole_2025', all_year=True),
    FinanceReportSpec(key='bank-5938-pdf1', label='Bank 5938 PDF 1',
                      dir='december_january_personal_bank_statement'),
    FinanceReportSpec(key='bank-6285-pdf1', label='Bank 6285 PDF 1',
                      dir='non_profit_rol_Statement_december_january_6285'),
    FinanceReportSpec(key='bank-6285-pdf2', label='Bank 6285 PDF 2',
                      dir='business_january_february_6285'),
    FinanceReportSpec(key='jetblue-pdf1', label='Jet Blue PDF 1',
                      dir='jet_blue__december_january_12_26_25_to_01_23_25'),
    FinanceReportSpec(key='jetblue-pdf2', label='Jet Blue PDF 2',
                      dir='jet_blue_january_february_01_27_to_02_25_25'),
    FinanceReportSpec(key='platinum-year', label='Platinum Year',
                      dir='platinum_business_credit_card_for_the_year',
                      all_year=True),
    FinanceReportSpec(key='diners-club-0587', label='Diners Club 0587',
                      dir='diners_club__january_25_statements-MONTHLY-0587'),
    FinanceReportSpec(key='diners-0587-year', label='Diners 0587 Year',
                      dir='diners_0587_whole_year_2025', all_year=True),
    FinanceReportSpec(key='bank-3119-pdf', label='Bank 3119 PDF',
                      dir='fifth_third_non_profit_3119'),
    FinanceReportSpec(key='choice-7580-year', label='Choice 7580 Year',
                      dir='choice_7580_year', all_year=True),
    FinanceReportSpec(key='prime-chase-5783', label='Prime Chase 5783',
                      dir='prime_chase_5783_whole_year_2025', all_year=True),
    FinanceReportSpec(key='amazon-marketplace', label='Amazon Marketplace',
                      dir='amazon_marketplace_january_2025', all_year=True),
)


def _check_the_registry_hangs_together() -> None:
    """Cross-entry invariants, plus the one that ties the two collections."""
    month_keys = [m.key for m in REPORT_MONTHS]
    if len(set(month_keys)) != len(month_keys):
        raise ValueError(f'duplicate month key in {month_keys}')
    folders = [m.folder for m in REPORT_MONTHS]
    if len(set(folders)) != len(folders):
        raise ValueError(
            f'two months share a folder in {folders} — one tab would list the '
            "other's reports")
    if DEFAULT_MONTH_KEY not in month_keys:
        raise ValueError(
            f'the default month {DEFAULT_MONTH_KEY!r} is not a month tab; the '
            'all-year cards would have nowhere to render and every unspecified '
            'request would fall through to a key that does not resolve')
    for field in ('key', 'label', 'dir'):
        values = [getattr(r, field) for r in FINANCE_REPORT_SPECS]
        if len(set(values)) != len(values):
            raise ValueError(f'two report cards share a {field}: {values}')


_check_the_registry_hangs_together()


# ── Derived views ─────────────────────────────────────────────────────────────

MONTH_KEYS: tuple[str, ...] = tuple(m.key for m in REPORT_MONTHS)

#: key -> the month's folder under ROL_FINANCES_REPORTS_PARENT.
ROL_FINANCES_REPORTS_MONTHS: dict[str, str] = {
    m.key: m.folder for m in REPORT_MONTHS
}

#: key -> (start, end), inclusive. Used by /api/rol-finance-month-status to find
#: that month's most-recently-scanned expense.
ROL_FINANCES_MONTH_RANGES: dict[str, tuple[str, str]] = {
    m.key: (m.start, m.end) for m in REPORT_MONTHS
}

ROL_FINANCE_REPORTS: list[dict] = [r.as_config() for r in FINANCE_REPORT_SPECS]


def reports_for_month(month_key: str) -> list[dict]:
    """Document cards for a month; all-year cards live only under January."""
    if month_key == DEFAULT_MONTH_KEY:
        return ROL_FINANCE_REPORTS
    return [r for r in ROL_FINANCE_REPORTS if not r.get('all_year')]


def resolve_month_key(requested: str | None) -> str:
    """The month tab a request is asking for, falling back to the default.

    The route ladder did this inline against two module globals. It is one
    question — *which month am I looking at?* — so it is one call.
    """
    return requested if requested in ROL_FINANCES_REPORTS_MONTHS else DEFAULT_MONTH_KEY
