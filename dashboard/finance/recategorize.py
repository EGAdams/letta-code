"""Setting a Verified-Transactions row's category, and taking it back.

One user gesture -- picking a bucket in the category dialog -- has to land in
two places that can disagree: the `expenses` row in the finance database, and
the `cat-*` class baked into the matching `<tr>` of a static report.html on
disk. `recategorize_expense` writes both; `undo_recategorize_expense` reverses
both through the tokenised journal in category_undo.py. The three travel
together because the undo has to repaint exactly the row the original write
painted, by exactly the same matching rules -- split them and the two sides
drift into disagreeing about which `<tr>` a transaction owns.

The undo journal's composition root lives here too. It is the only caller of
`CategoryUndoService`, and its journal path is a constant nothing else reads.

Everything that stays behind in server.py arrives as a `Collaborators` bundle
built fresh on every call, never imported: `_rol_get_connection`,
`_resolve_reporting_category`, `_find_matching_report_row` and the rest are the
names the existing tests monkeypatch on `server`, and an import-time binding
here would silently detach this module from those patches while still looking
exactly like it was patched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from category_undo import (
    CategoryChange,
    CategoryUndoService,
    JsonCategoryUndoStore,
    MySqlCategoryRepository,
)
from paths import HERE

import os
import threading

#: Where the one-shot undo tokens are journalled. Read by nothing else.
CATEGORY_UNDO_JOURNAL = os.path.join(HERE, 'category_undo_journal.json')

#: The only shape a category class may have. Report files bake these into every
#: `<tr>`, and `_swap_cls` below strips exactly this pattern when repainting a
#: row -- so a value that does not match it can never be removed again.
CATEGORY_CLASS_PATTERN = r'^cat-[a-z0-9-]+$'


class ReportRowClass(BaseModel):
    """The single `cat-*` class this module is allowed to splice into a report.

    The strip pattern in `_swap_cls` is the report file's real contract, but
    nothing used to check the value going *in* against it. The class comes from
    the categories table's `css_class` column by way of the taxonomy -- a plain
    untyped string out of a database -- and it is written straight into a
    `class="..."` attribute in a file on disk. A value with a space silently
    added a second class; one with a quote broke out of the attribute and
    corrupted a report nobody opens until a month-end review; and either one
    then survives every later re-categorisation, because the strip cannot match
    it to take it back out. Checked here, once, at the only place that writes.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    value: str

    @field_validator('value')
    @classmethod
    def _must_be_a_cat_class(cls, value: str) -> str:
        if not re.match(CATEGORY_CLASS_PATTERN, value or ''):
            raise ValueError(
                f'not a cat-* class: {value!r} (must match {CATEGORY_CLASS_PATTERN})')
        return value


class RecategorizeRequest(BaseModel):
    """One category pick, as it arrives from the browser.

    Two fields used to accept garbage in silence:

    `expense_id` went through a bare `int()`, so a JSON `3.9` became expense 3
    and `true` became expense 1 -- a confident UPDATE against a real row that
    is not the one the user clicked. Only an integer, or a string of digits,
    is a row id.

    `signed_amount` went through `Decimal()`, which accepts `'nan'` and
    `'inf'`. `WHERE amount='NaN'` matches nothing, so the lookup fell through
    to the not-in-the-database branch and answered `ok: True` with "color saved
    to report only" -- a success message for a transaction that was never
    checked. Only a finite decimal is an amount.

    Amount parsing is conditional, exactly as the hand-rolled version was: with
    an `expense_id` in hand the row is found by id and `signed_amount` is
    display text that never reaches SQL.
    """

    model_config = ConfigDict(extra='forbid')

    date: str = ''
    signed_amount: str = ''
    vendor_key: str = ''
    reporting_category: str = ''
    description: str = ''
    report_path: str = ''
    expense_id: Optional[int] = None
    #: abs(signed_amount) as a Decimal, and only when there is no expense_id.
    amount: Optional[Decimal] = None

    @field_validator('expense_id', mode='before')
    @classmethod
    def _row_id_only(cls, value):
        if value is None or value == '':
            return None
        if isinstance(value, bool):
            raise ValueError('expense_id is a row id, not a flag')
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r'\s*\d+\s*', value):
            return int(value)
        raise ValueError('expense_id is not a whole row id')

    @model_validator(mode='after')
    def _parse_amount(self):
        if self.expense_id is not None:
            return self
        raw = str(self.signed_amount or '').replace('$', '').replace(',', '').strip()
        try:
            parsed = Decimal(raw)
        except (InvalidOperation, ValueError):
            raise ValueError('signed_amount is not a number')
        if not parsed.is_finite():
            raise ValueError('signed_amount is not a finite amount')
        self.amount = abs(parsed)
        return self

    @classmethod
    def from_call(cls, date_str, signed_amount, vendor_key, reporting_category,
                  description, report_path, expense_id):
        """Build the request, or return the error dict the caller used to return.

        Returns `(request, None)` or `(None, error_dict)`. The error text is
        byte-identical to the hand-rolled parsing it replaced, so the browser
        sees the same payload it always did.
        """
        try:
            return cls(
                date=str(date_str or ''),
                signed_amount=str(signed_amount or ''),
                vendor_key=str(vendor_key or ''),
                reporting_category=str(reporting_category or ''),
                description=str(description or ''),
                report_path=str(report_path or ''),
                expense_id=expense_id,
            ), None
        except ValidationError as exc:
            location = exc.errors()[0]['loc']
            if location and location[0] == 'expense_id':
                return None, {'ok': False, 'error': f'Bad expense_id: {expense_id!r}'}
            return None, {'ok': False, 'error': f'Bad amount: {signed_amount!r}'}


@dataclass(frozen=True)
class Collaborators:
    """What this cluster needs that stays behind in server.py.

    server.py's wrappers build one of these per call rather than at import, so
    `monkeypatch.setattr(server, '_rol_get_connection', ...)` still reaches the
    code that actually runs. Bind any of these at import time and the patch
    lands on a name nothing calls any more.
    """

    get_connection: Callable
    resolve_reporting_category: Callable
    css_class_for_report_name: Callable
    find_matching_report_row: Callable
    report_file_for_url: Callable
    vendor_prefix: Callable
    category_taxonomy: Callable
    receipt_only_report_path: str


_category_undo_service = None
_category_undo_service_lock = threading.Lock()


def _get_category_undo_service(get_connection):
    """Composition root for the interface-backed category undo boundary."""
    global _category_undo_service
    with _category_undo_service_lock:
        if _category_undo_service is None:
            _category_undo_service = CategoryUndoService(
                JsonCategoryUndoStore(CATEGORY_UNDO_JOURNAL),
                MySqlCategoryRepository(get_connection),
            )
    return _category_undo_service


def _record_category_undo(action, get_connection):
    return _get_category_undo_service(get_connection).record(CategoryChange(**action))


def _undo_category_action(token, get_connection):
    return _get_category_undo_service(get_connection).undo(token)


def update_report_row_color(report_path, vendor_key, date_str, amount_str, new_cls,
                            expense_id=None, *, report_file_for_url):
    """Rewrite the cat-* class on the matching Verified-Transactions <tr> on disk.

    Identifies the row by data-vendor-key + the displayed date and amount cells, so
    the saved color is permanent across page refreshes. Returns True if a row changed.

    Refuses -- without touching the file -- when `new_cls` is not a `cat-*`
    class. A repaint that does not happen shows up as `file_updated: False`; a
    malformed class spliced into the attribute is a corrupted report file, and
    of the two only one is recoverable.
    """
    try:
        new_cls = ReportRowClass(value=str(new_cls or '')).value
    except ValidationError as exc:
        print(f'[recategorize] action=paint status=refused reason={exc.errors()[0]["msg"]}')
        return False
    fp = report_file_for_url(report_path)
    if not fp:
        return False
    with open(fp, encoding='utf-8') as f:
        html = f.read()

    vk = (vendor_key or '').strip()
    d = (date_str or '').strip()
    a = (amount_str or '').strip()
    eid = str(expense_id or '').strip()
    if not eid and not vk:
        return False

    def attempt(require_date, require_amount):
        """Rewrite the first vendor-matching row that also meets the given criteria."""
        state = {'done': False}

        def repl(m):
            open_tag, inner = m.group(1), m.group(2)
            if state['done']:
                return m.group(0)
            if eid:
                if ('data-expense-id="%s"' % eid) not in open_tag:
                    return m.group(0)
            else:
                if ('data-vendor-key="%s"' % vk) not in open_tag:
                    return m.group(0)
                if require_date and d and ('>%s<' % d) not in inner:
                    return m.group(0)
                if require_amount and a and ('>%s<' % a) not in inner:
                    return m.group(0)
            # Replace ALL cat-* classes in the class attribute so re-categorizing
            # a row doesn't leave stale old classes behind (or double-add when the
            # same category is picked twice).
            def _swap_cls(cm):
                parts = [p for p in cm.group(1).split()
                         if not re.match(r'^cat-[a-z0-9-]+$', p)]
                return 'class="%s"' % ' '.join([new_cls] + parts)
            has_class_attr = 'class="' in open_tag
            new_open = re.sub(r'class="([^"]*)"', _swap_cls, open_tag, count=1)
            if not has_class_attr:  # row had no class attribute at all
                new_open = open_tag + ' class="%s"' % new_cls
            state['done'] = True
            return '<tr%s>%s</tr>' % (new_open, inner)

        out = re.sub(r'<tr([^>]*)>(.*?)</tr>', repl, html, flags=re.S)
        return out if state['done'] else None

    attempts = ((False, False),) if eid else ((True, True), (True, False), (False, True))
    for require_date, require_amount in attempts:
        out = attempt(require_date, require_amount)
        if out is not None:
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(out)
            return True
    return False


def recategorize_expense(date_str, signed_amount, vendor_key, reporting_category,
                         description='', report_path='', expense_id=None, *, deps):
    """Persist a user's category pick for one Verified-Transactions row.

    Uses expense_id when the row provides it. Legacy standalone report rows fall
    back to (expense_date, abs(amount)); LINE_ITEM rows must provide an ID because
    siblings can share both date and amount.
    """
    # Resolve through the taxonomy (the categories table), not the frozen dict,
    # so buckets added by a migration are selectable the moment they exist.
    target_id, _target_cls = deps.resolve_reporting_category(reporting_category)
    if _target_cls is None:
        return {'ok': False, 'error': f'Unknown category: {reporting_category}'}

    request, error = RecategorizeRequest.from_call(
        date_str, signed_amount, vendor_key, reporting_category,
        description, report_path, expense_id)
    if error is not None:
        return error
    target_expense_id = request.expense_id
    amt = request.amount

    try:
        with deps.get_connection() as cnx:
            with cnx.cursor() as cur:
                def _find_expense(d):
                    if target_expense_id is not None:
                        cur.execute(
                            "SELECT id, id_light, description, category_id, expense_role "
                            "FROM expenses WHERE id=%s",
                            (target_expense_id,),
                        )
                        return cur.fetchall()
                    cur.execute(
                        "SELECT id, id_light, description, category_id, expense_role "
                        "FROM expenses WHERE expense_date=%s AND amount=%s "
                        "AND expense_role='STANDALONE'",
                        (d, str(amt)),
                    )
                    return cur.fetchall()

                rows = _find_expense(date_str)
                # Credit-card posting dates are often 1-3 days after the purchase
                # date stored in the DB. Try nearby dates when exact lookup fails.
                if not rows and target_expense_id is None:
                    try:
                        base = datetime.strptime(date_str, '%Y-%m-%d').date()
                        for delta in (-1, 1, -2, 2, -3, 3):
                            alt = (base + timedelta(days=delta)).isoformat()
                            rows = _find_expense(alt)
                            if rows:
                                break
                    except (ValueError, AttributeError):
                        pass
                if not rows:
                    if target_expense_id is not None:
                        return {'ok': False,
                                'error': f'Expense {target_expense_id} was not found.'}
                    # Transaction not in DB (e.g. annual summary never imported).
                    # Still persist the color in the HTML file so the pick survives
                    # a page refresh, and return ok so the dialog closes cleanly.
                    file_updated = False
                    if report_path and report_path != deps.receipt_only_report_path:
                        try:
                            new_cls = _target_cls
                            if new_cls:
                                file_updated = update_report_row_color(
                                    report_path, vendor_key, date_str,
                                    signed_amount, new_cls,
                                    expense_id=target_expense_id,
                                    report_file_for_url=deps.report_file_for_url)
                        except Exception:
                            pass
                    return {'ok': True, 'expense_id': None,
                            'file_updated': file_updated,
                            'warning': 'Transaction not in DB — color saved to report only.'}

                if len(rows) == 1:
                    chosen = rows[0]
                else:
                    chosen = None
                    vk = (vendor_key or '').strip()
                    for r in rows:
                        vp = deps.vendor_prefix(r.get('id_light'))
                        if vk and vp and (vk.startswith(vp) or vp.startswith(vk)):
                            chosen = r
                            break
                    if chosen is None and description:
                        for r in rows:
                            if (r.get('description') or '').strip() == description.strip():
                                chosen = r
                                break
                    if chosen is None:
                        return {'ok': False,
                                'error': f'{len(rows)} expenses share that date/amount; '
                                         'could not pinpoint which one.'}

                if chosen.get('expense_role') == 'PARENT':
                    return {'ok': False,
                            'error': 'A PARENT is a reconciliation anchor and cannot be categorized.'}

                cur.execute("UPDATE expenses SET category_id=%s WHERE id=%s",
                            (target_id, chosen['id']))
    except Exception as e:
        return {'ok': False, 'error': f'DB error: {e}'}

    # Persist the color into the static report.html so it survives a refresh.
    file_updated = False
    matched_report = None
    if report_path == deps.receipt_only_report_path:
        # The Receipt Only tab is a dynamic page rebuilt from the DB on every
        # load — the DB write above is the whole change.
        file_updated = True
    elif not report_path:
        # The New Records dialog doesn't know which report.html (if any) this
        # transaction lives in — search for it instead of assuming there is none
        # (see _find_matching_report_row: DB vs. bank-statement vendor_key spelling
        # often diverges, so a plain report_path lookup can't be done client-side).
        try:
            new_cls = _target_cls
            report_expense_id = (
                chosen['id'] if chosen.get('expense_role') == 'LINE_ITEM' else None)
            found = deps.find_matching_report_row(
                date_str, signed_amount, vendor_key, report_expense_id) if new_cls else None
            if found:
                if update_report_row_color(
                        found.report_path, found.row_vendor_key,
                        date_str, signed_amount, new_cls,
                        expense_id=report_expense_id,
                        report_file_for_url=deps.report_file_for_url):
                    file_updated = True
                    matched_report = {'report_path': found.report_path, 'label': found.label}
        except Exception:
            pass
        if not matched_report:
            # Genuinely no static row anywhere (e.g. a standalone receipt with no
            # matching bank transaction) — the DB write above is the whole change.
            file_updated = True
    else:
        try:
            new_cls = _target_cls
            if new_cls:
                # Match the file by the RAW displayed amount the client sent (e.g. "-$150.00",
                # "+$10.00", "296.41") — NOT the normalized abs value used for the DB lookup,
                # which would only match plain rows like "10.25".
                file_updated = update_report_row_color(
                    report_path, vendor_key, date_str, signed_amount, new_cls,
                    expense_id=(chosen['id']
                                if chosen.get('expense_role') == 'LINE_ITEM'
                                else None),
                    report_file_for_url=deps.report_file_for_url)
        except Exception:
            file_updated = False

    previous_category_id = chosen.get('category_id')
    # Walk the tree rather than doing a flat lookup. REPORTING_CATEGORY_ANCESTOR_MAP
    # only covers 24 of 169 categories, so the old `.get(..., 'Uncategorized')`
    # mislabelled every expense stored on a leaf — 280 of 892 categorised rows —
    # and undo then repainted them grey instead of their real bucket colour.
    previous_reporting_category = deps.category_taxonomy().label_for(
        previous_category_id)
    try:
        undo_token = _record_category_undo({
            'expense_id': int(chosen['id']),
            'previous_category_id': previous_category_id,
            'category_id': target_id,
            'previous_reporting_category': previous_reporting_category,
            'reporting_category': reporting_category,
            'date': str(date_str or ''),
            'signed_amount': str(signed_amount or ''),
            'vendor_key': str(vendor_key or ''),
            'description': str(description or chosen.get('description') or ''),
            'report_path': (
                matched_report['report_path'] if matched_report else report_path or ''
            ),
        }, deps.get_connection)
    except Exception as exc:
        print(
            '[category-undo] action=record status=failed '
            f'expense_id={chosen["id"]} error={type(exc).__name__}'
        )
        undo_token = None

    return {
        'ok': True,
        'expense_id': chosen['id'],
        'previous_category_id': previous_category_id,
        'category_id': target_id,
        'reporting_category': reporting_category,
        'file_updated': file_updated,
        'matched_report': matched_report,
        'undo_token': undo_token,
    }


def undo_recategorize_expense(token, *, deps):
    """Undo one tokenized category write without overwriting a newer choice."""
    result = _undo_category_action(str(token or '').strip(), deps.get_connection)
    if result.get('status') not in {'restored', 'already_restored'}:
        return {'ok': False, 'error': result.get('error', 'Undo failed.')}

    action = result['action']
    previous_reporting_category = action['previous_reporting_category']
    previous_class = deps.css_class_for_report_name(previous_reporting_category)
    report_path = action.get('report_path') or ''
    file_updated = report_path == deps.receipt_only_report_path

    if report_path and report_path != deps.receipt_only_report_path:
        file_updated = update_report_row_color(
            report_path,
            action.get('vendor_key', ''),
            action.get('date', ''),
            action.get('signed_amount', ''),
            previous_class,
            expense_id=action['expense_id'],
            report_file_for_url=deps.report_file_for_url,
        )
        if not file_updated:
            file_updated = update_report_row_color(
                report_path,
                action.get('vendor_key', ''),
                action.get('date', ''),
                action.get('signed_amount', ''),
                previous_class,
                report_file_for_url=deps.report_file_for_url,
            )
    elif not report_path:
        found = deps.find_matching_report_row(
            action.get('date', ''),
            action.get('signed_amount', ''),
            action.get('vendor_key', ''),
            action['expense_id'],
        )
        if found:
            file_updated = update_report_row_color(
                found.report_path,
                found.row_vendor_key,
                action.get('date', ''),
                action.get('signed_amount', ''),
                previous_class,
                expense_id=action['expense_id'],
                report_file_for_url=deps.report_file_for_url,
            )
        else:
            file_updated = True

    return {
        'ok': True,
        'status': result['status'],
        'expense_id': action['expense_id'],
        'category_id': action['previous_category_id'],
        'reporting_category': previous_reporting_category,
        'category_class': previous_class,
        'file_updated': file_updated,
    }
