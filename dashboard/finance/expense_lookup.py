"""Rows for the synthetic recent-intake view, by expense id.

``fetch_expenses_by_ids`` is what turns a STEP 8 callback's ``expense_ids``
into the same row shape the Receipt Only tab renders, so the shared picker
markup drives both identically. It also expands a PARENT reconciliation
anchor into its categorizable LINE_ITEM children -- the picker refuses a
PARENT outright (see ``finance.recategorize``), so an intake that only knows
the anchor id needs its children substituted before the table is clickable.

``get_connection``, ``reporting_category_for_id`` and
``css_class_for_report_name`` all stay behind in server.py -- each is reused
by several other routes -- so they arrive as a ``Collaborators`` bundle built
fresh per call, same reasoning as ``finance.recategorize.Collaborators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from finance.expense_schema import InformationSchemaProbe


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable
    reporting_category_for_id: Callable
    css_class_for_report_name: Callable


def fetch_expenses_by_ids(deps: Collaborators, ids):
    """Rows for the synthetic recent-intake view -- same shape as the Receipt
    Only rows so the shared picker markup drives them identically.

    A PARENT is a reconciliation anchor and carries no category of its own, so
    the picker refuses it (see finance.recategorize.recategorize_expense).
    When STEP 8 reports a PARENT id we therefore substitute its LINE_ITEM
    children -- those are the rows that actually hold the category -- so the
    intake page shows something the user can click and set. The child
    description is prefixed with the parent's (e.g. "Consumers Energy —
    Amount Due") so the vendor is still recognizable in the table."""
    clean = []
    for i in ids or []:
        try:
            clean.append(int(i))
        except (TypeError, ValueError):
            continue
    clean = clean[:200]
    if not clean:
        return []
    placeholders = ','.join(['%s'] * len(clean))
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            cur.execute('SELECT id, parent_id FROM categories')
            parent_of = {
                int(r['id']): (int(r['parent_id']) if r['parent_id'] is not None else None)
                for r in cur.fetchall()
            }
            cur.execute(
                "SELECT 1 AS present FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'expenses' "
                "AND COLUMN_NAME = 'expense_role' LIMIT 1")
            has_expense_roles = bool(cur.fetchone())
            role_select = ', expense_role' if has_expense_roles else ''
            # A narrower live schema must not fail the whole page: absent
            # optional columns come back as NULL (see finance.expense_schema).
            optional_columns = (
                'id_light', 'receipt_url', 'document_url',
                'scanned_statement_url', 'moms_ledger', 'source_file',
                'human_verified',
            )
            schema = InformationSchemaProbe().read(cur, optional_columns)
            select_sql = schema.select_clause(
                ('id', 'expense_date', 'amount', 'description', 'category_id'),
                optional_columns,
            )
            cur.execute(
                f"SELECT {select_sql}{role_select} "
                f"FROM expenses WHERE id IN ({placeholders}) "
                "ORDER BY expense_date, id",
                tuple(clean),
            )
            rows = cur.fetchall()

            # Expand each PARENT anchor into its categorizable LINE_ITEM children.
            parent_ids = [int(r['id']) for r in rows
                          if has_expense_roles
                          and (r.get('expense_role') or '') == 'PARENT']
            if parent_ids:
                parent_desc = {int(r['id']): (r.get('description') or '').strip()
                               for r in rows}
                ph2 = ','.join(['%s'] * len(parent_ids))
                cur.execute(
                    "SELECT id, expense_date, amount, id_light, description, category_id, "
                    "receipt_url, document_url, scanned_statement_url, moms_ledger, "
                    f"{('source_file' if schema.has('source_file') else 'NULL AS source_file')}, "
                    f"{('human_verified' if schema.has('human_verified') else '0 AS human_verified')}, "
                    "expense_role, parent_expense_id "
                    f"FROM expenses WHERE parent_expense_id IN ({ph2}) "
                    "AND expense_role='LINE_ITEM' "
                    "ORDER BY expense_date, id",
                    tuple(parent_ids),
                )
                children = cur.fetchall()
                child_by_parent = {}
                for ch in children:
                    pdesc = parent_desc.get(int(ch.get('parent_expense_id') or 0), '')
                    cdesc = (ch.get('description') or '').strip()
                    if pdesc and cdesc and pdesc.lower() not in cdesc.lower():
                        ch['description'] = f'{pdesc} — {cdesc}'
                    child_by_parent.setdefault(
                        int(ch['parent_expense_id']), []).append(ch)
                # STEP 8 reports the anchor AND the children it created, so a
                # child is usually in `rows` already. Keyed by id, the spliced
                # copy wins: it is the one carrying the parent's vendor prefix.
                expanded = {}
                for r in rows:
                    if (r.get('expense_role') or '') == 'PARENT':
                        # Drop the anchor; show its children instead. A parent
                        # with no children left (data anomaly) is simply omitted
                        # rather than shown as an uncategorizable dead row.
                        for ch in child_by_parent.get(int(r['id']), []):
                            expanded[int(ch['id'])] = ch
                    else:
                        expanded.setdefault(int(r['id']), r)
                rows = sorted(
                    expanded.values(),
                    key=lambda r: (str(r.get('expense_date') or ''), int(r['id'])),
                )
    out = []
    for r in rows:
        cid = r.get('category_id')
        rep = deps.reporting_category_for_id(
            int(cid) if cid is not None else None, parent_of)
        out.append({
            'id': int(r['id']),
            'date': str(r['expense_date']),
            'amount': str(r['amount']),
            'id_light': (r.get('id_light') or '').strip(),
            # Filled from the display/source description immediately before
            # rendering; never conflate id_light with a reusable vendor key.
            'vendor_key': '',
            'description': (r.get('description') or '').strip(),
            'reporting_category': rep,
            'cat_class': deps.css_class_for_report_name(rep),
            'receipt_url': (r.get('receipt_url') or '').strip(),
            'document_url': (r.get('document_url') or '').strip(),
            'scanned_statement_url': (r.get('scanned_statement_url') or '').strip(),
            'moms_ledger': (r.get('moms_ledger') or '').strip(),
            'source_file': (r.get('source_file') or '').strip(),
            'human_verified': bool(r.get('human_verified')),
        })
    return out
