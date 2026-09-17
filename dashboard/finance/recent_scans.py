"""The recently-scanned queue and the green/yellow/red month-tab status.

A scanned receipt becomes an `expenses` row (created_at auto-set on INSERT), so
"recently scanned, newest first" is just ORDER BY created_at DESC — no separate
queue store is needed. Registries (`ROL_FINANCE_REPORTS`, the month ranges) are
rebound wholesale by tests to point at a tmp_path fixture tree, and
``month_broken_report_label`` is itself monkeypatched directly, so all of it
arrives fresh via ``Collaborators`` rather than being captured at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from finance.reporting_category_lookup import account_number_in_label

#: category_id NULL, or 1/364 which both resolve to 'Uncategorized' in
#: REPORTING_CATEGORY_ANCESTOR_MAP (the same buckets the picker's
#: "Uncategorized" choice writes back, i.e. category_id -> None).
UNCATEGORIZED_CATEGORY_IDS = (1, 364)


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable
    norm_amount: Callable
    resolve_expense_receipt_path: Callable
    reporting_category_for_id: Callable
    css_class_for_report_name: Callable
    vendor_prefix: Callable
    month_broken_report_label: Callable
    reports: list
    month_ranges: dict
    reports_default_month: str


def is_uncategorized(category_id):
    """True when an expense row still needs a category (the 'unfinished' state)."""
    return category_id is None or int(category_id) in UNCATEGORIZED_CATEGORY_IDS


def document_report_for_path(deps: Collaborators, path, month_key=None):
    """Which report card (tab) a stored document/receipt path belongs to — so an
    uncategorized expense's reason can say which tab to fix it on.

    The source PDF for a bank/card statement usually does NOT live under the
    report card's own `dir` (that folder holds the generated report.html,
    built separately); it is a flat file under scanned_statements/ named after
    the account, e.g. `fifth_third_bank_3119_february_14__february_28.pdf`.
    So the primary signal is the account number embedded in both the filename
    and the card's label — falling back to a `dir` match for the cases (e.g.
    supporting documents) where the path genuinely does pass through it.
    Several numbers repeat across cards (a monthly card and its year-summary
    twin, or two PDFs off the same account); among ties this prefers the card
    scoped to `month_key`, then a monthly (non all-year) card, over guessing.
    None when nothing matches.
    """
    if not path:
        return None
    filename = path.rsplit('/', 1)[-1]
    import re
    numbers = set(re.findall(r'\d{3,4}', filename))
    if numbers:
        candidates = [
            r for r in deps.reports
            if account_number_in_label(r['label']) in numbers
        ]
        if candidates:
            chosen = (
                next((c for c in candidates if c.get('only_month') == month_key), None)
                or next((c for c in candidates if not c.get('all_year')), None)
                or candidates[0])
            return {'key': chosen['key'], 'label': chosen['label']}
    parts = path.split('/')
    for r in deps.reports:
        if r.get('dir') in parts:
            return {'key': r['key'], 'label': r['label']}
    return None


def fetch_receipt_only_rows(deps: Collaborators, month_key=None):
    """expenses with no matching bank-statement transaction (same date + abs amount)
    AND a receipt file that actually resolves on disk, each tagged with its current
    reporting category. The resolve check keeps the tab in lockstep with the red
    has-receipt marker so every row shown genuinely has a receipt."""
    # January is the intentionally special all-year receipt display. Every
    # other configured month is restricted to its own calendar date range.
    month_range = None if month_key == deps.reports_default_month else \
        deps.month_ranges.get(month_key)
    date_clause = ''
    date_params = ()
    if month_range:
        date_clause = ' AND e.expense_date BETWEEN %s AND %s'
        date_params = month_range
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute('SELECT id, parent_id FROM categories')
            parent_of = {
                int(r['id']): (int(r['parent_id']) if r['parent_id'] is not None else None)
                for r in cur.fetchall()
            }
            cur.execute(
                "SELECT e.id, e.expense_date, e.amount, e.id_light, e.description, "
                "       e.category_id, e.receipt_url, e.document_url, "
                "       e.moms_ledger, e.expense_role, e.human_verified "
                "FROM expenses e "
                "WHERE e.expense_role <> 'PARENT' "
                "AND NOT EXISTS (SELECT 1 FROM transactions t "
                "                  WHERE t.transaction_date=e.expense_date "
                "                    AND ABS(t.amount)=ABS(e.amount)) "
                f"{date_clause} "
                "ORDER BY e.expense_date, e.id",
                date_params,
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        date_str = str(r['expense_date'])
        amt = deps.norm_amount(r['amount'])
        if amt is None:
            continue
        # Only include rows whose receipt file actually exists (same resolution the
        # has-receipt marker uses). Excludes the receipt_url-but-no-file data gap.
        if not deps.resolve_expense_receipt_path(date_str, amt, r.get('receipt_url')):
            continue
        cid = r.get('category_id')
        rep = deps.reporting_category_for_id(
            int(cid) if cid is not None else None, parent_of)
        out.append({
            'id': int(r['id']),
            'date': date_str,
            'amount': str(r['amount']),
            'vendor_key': (r.get('id_light') or '').strip(),
            'description': (r.get('description') or '').strip(),
            'reporting_category': rep,
            'cat_class': deps.css_class_for_report_name(rep),
            'receipt_url': r.get('receipt_url'),
            'document_url': r.get('document_url'),
            'moms_ledger': r.get('moms_ledger'),
            'human_verified': bool(r.get('human_verified')),
        })
    return out


def fetch_recent_scans(deps: Collaborators, limit=5, month_key=None):
    """The most-recently-scanned expenses that are still uncategorized, newest
    first — the 'recently scanned viewing area'. Returning only up to `limit`
    unfinished rows IS the 'keep the view at <=5, backfill the next one' rule:
    as each row gets categorized it drops out and the next surfaces. Also returns
    queue_total = how many uncategorized rows are waiting overall."""
    limit = max(1, min(int(limit or 5), 50))
    month_range = deps.month_ranges.get(month_key)
    where_suffix = ''
    where_params = ()
    if month_range:
        where_suffix = ' AND expense_date BETWEEN %s AND %s'
        where_params = month_range
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute(
                "SELECT id, id_light, description, expense_date, amount, "
                "       category_id, receipt_url, document_url, source_file, "
                "       moms_ledger, created_at, notes, address, map_link "
                "FROM expenses "
                "WHERE (category_id IS NULL OR category_id IN (%s, %s))"
                " AND expense_role <> 'PARENT'"
                f"{where_suffix} "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (*UNCATEGORIZED_CATEGORY_IDS, *where_params, limit),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) AS n FROM expenses "
                "WHERE (category_id IS NULL OR category_id IN (%s, %s))"
                " AND expense_role <> 'PARENT'"
                f"{where_suffix}",
                (*UNCATEGORIZED_CATEGORY_IDS, *where_params),
            )
            total = int(cur.fetchone()['n'])
    out = []
    for r in rows:
        date_str = str(r['expense_date'])
        amt = deps.norm_amount(r['amount'])
        # Why this record is in "New Records": prefer a specific note written by
        # the intake pipeline / Mazda (expenses.notes); otherwise the generic
        # reason it lands here — categorization never completed.
        notes = (r.get('notes') or '').strip()
        reason = notes or (
            'Categorization incomplete — no reporting category was assigned. '
            'Pick one, or ask Mazda how to resolve it.')
        out.append({
            'id': int(r['id']),
            'vendor_key': deps.vendor_prefix(r.get('id_light')),
            'id_light': (r.get('id_light') or '').strip(),
            'description': (r.get('description') or '').strip(),
            'expense_date': date_str,
            'amount': str(r['amount']),
            'created_at': str(r.get('created_at') or ''),
            'reporting_category': 'Uncategorized',
            'reason': reason,
            'receipt_present': bool(
                deps.resolve_expense_receipt_path(date_str, amt, r.get('receipt_url'))
                if amt is not None else False),
            'receipt_url': r.get('receipt_url') or '',
            'document_url': r.get('document_url') or '',
            'address': r.get('address') or '',
            'map_link': r.get('map_link') or '',
            'document_report': (
                document_report_for_path(deps, r.get('document_url'), month_key)
                or document_report_for_path(deps, r.get('receipt_url'), month_key)
                or document_report_for_path(deps, r.get('source_file'), month_key)),
            'moms_ledger': r.get('moms_ledger') or '',
        })
    return {'rows': out, 'queue_total': total, 'limit': limit, 'month_key': month_key}


def fetch_month_status(deps: Collaborators):
    """Per-month status for the report month tabs. 'red' when any of the
    month's report.html cards is missing or fails verification — a document
    problem outranks the expense signal below. Otherwise 'yellow' (work to
    do) when the most-recently-scanned expense is still uncategorized, else
    'green'. The yellow/green check keys off the most-recent scan to match
    the spec: the tab reacts to the newest document's unfinished business."""
    result = []
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            for month_key, (start, end) in deps.month_ranges.items():
                cur.execute(
                    "SELECT id, id_light, description, expense_date, amount, "
                    "       category_id, created_at "
                    "FROM expenses WHERE expense_date BETWEEN %s AND %s "
                    "AND expense_role <> 'PARENT' "
                    "ORDER BY created_at DESC, id DESC LIMIT 1",
                    (start, end),
                )
                newest = cur.fetchone()
                cur.execute(
                    "SELECT COUNT(*) AS n FROM expenses "
                    "WHERE expense_date BETWEEN %s AND %s "
                    "AND expense_role <> 'PARENT' "
                    "AND (category_id IS NULL OR category_id IN (%s, %s))",
                    (start, end, *UNCATEGORIZED_CATEGORY_IDS),
                )
                uncat = int(cur.fetchone()['n'])
                if newest is None:
                    status = 'green'
                    most_recent = None
                else:
                    unfinished = is_uncategorized(newest.get('category_id'))
                    status = 'yellow' if unfinished else 'green'
                    most_recent = {
                        'id': int(newest['id']),
                        'vendor_key': deps.vendor_prefix(newest.get('id_light')),
                        'description': (newest.get('description') or '').strip(),
                        'expense_date': str(newest['expense_date']),
                        'amount': str(newest['amount']),
                        'uncategorized': unfinished,
                    }
                broken_report_label = deps.month_broken_report_label(month_key)
                if broken_report_label:
                    status = 'red'
                result.append({
                    'month_key': month_key,
                    'status': status,
                    'uncategorized_count': uncat,
                    'broken_report_label': broken_report_label,
                    'most_recent_unfinished': most_recent,
                })
    return result
