"""Resolving a receipt file on disk from what an expense row knows about it.

The receipt index (`_build_receipt_index`/`receipt_index`) is a filesystem
crawl of every receipt mount, cached for `RECEIPT_INDEX_TTL` seconds so the
Receipt Only page and View Receipt button don't re-walk the tree on every
request. ``RECEIPT_MOUNTS`` is rebound wholesale by several tests (external
Windows-side store simulation), so it arrives fresh per call via
``Collaborators`` rather than being captured at import time. ``cache`` is the
same dict object server.py exposes as ``_RECEIPT_INDEX_CACHE`` -- a test
mutates it in place (``.update(...)``), so it has to stay one shared object,
never rebuilt here. ``receipt_index`` and ``resolve_receipt_url_path`` route
back through the server.py names (not this module's own functions) because
tests monkeypatch each individually to drive ``resolve_expense_receipt_path``
without a real filesystem -- same reasoning as
``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.parse import quote

from finance.expense_schema import ShowColumnsProbe
from finance.receipt_filename import parse_receipt_filename


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    receipt_mounts: list
    readable_docs_base: str
    receipts_url_prefix: str
    cache: dict
    cache_ttl: float
    vendor_prefix: Callable
    receipt_index: Callable
    resolve_receipt_url_path: Callable


def norm_amount(signed_amount):
    raw = str(signed_amount or '').replace('$', '').replace(',', '').strip()
    try:
        return str(abs(Decimal(raw)))
    except (InvalidOperation, ValueError):
        return None


def build_receipt_index(deps: Collaborators):
    by_da, by_stem = {}, {}
    seen = set()
    # Walk every receipt index subtree (canonical readable_documents/receipts plus
    # any external store such as the Windows-side live-pipeline destination). The
    # canonical tree is walked first, so a file present in both keeps its canonical
    # path (and dedupe below prevents the external copy from being added twice).
    for _prefix, _base, subtree in deps.receipt_mounts:
        if not os.path.isdir(subtree):
            continue
        for root, _dirs, files in os.walk(subtree):
            for fn in files:
                fp = os.path.join(root, fn)
                rp = os.path.realpath(fp)
                if rp in seen:
                    continue
                seen.add(rp)
                by_stem.setdefault(os.path.splitext(fn)[0].lower(), []).append(fp)
                match = parse_receipt_filename(fn)
                if match:
                    by_da.setdefault(match.index_key(), []).append(fp)
    return by_da, by_stem


def receipt_index(deps: Collaborators):
    now = time.time()
    if (deps.cache['by_da'] is None
            or now - deps.cache['ts'] > deps.cache_ttl):
        by_da, by_stem = build_receipt_index(deps)
        deps.cache.update(ts=now, by_da=by_da, by_stem=by_stem)
    return deps.cache['by_da'], deps.cache['by_stem']


def resolve_receipt_url_path(deps: Collaborators, receipt_url):
    """Resolve one expense's non-empty receipt_url to a local receipt file.

    Searches every receipt mount (canonical readable_documents store + any external
    store such as the live-pipeline Windows destination), so a receipt_url that
    names a file in either tree resolves.
    """
    _by_da, by_stem = deps.receipt_index()
    ru = (receipt_url or '').strip().lstrip('/')
    if not ru:
        return None
    # Direct path under any serve base (path-traversal guarded).
    for _prefix, serve_base, _subtree in deps.receipt_mounts:
        base = os.path.abspath(serve_base)
        direct = os.path.abspath(os.path.join(base, ru))
        if os.path.commonpath([direct, base]) == base and os.path.isfile(direct):
            return direct
    stem = os.path.splitext(os.path.basename(ru))[0].lower()
    if stem in by_stem:
        return by_stem[stem][0]
    # by_stem already indexes every basename under every receipt subtree. Do
    # not repeat recursive glob walks for missing files: a month can contain
    # dozens of stale receipt_url values and those redundant scans made the
    # Receipt Only page appear blank for 10+ seconds.
    return None


def resolve_expense_receipt_path(deps: Collaborators, date_str, amount_str, receipt_url):
    """Resolve a receipt only for an expense that owns a non-empty receipt_url.

    Stored receipt_url values are not always byte-for-byte file paths, so after
    trying the URL directly we retain the established date/amount filename
    fallback. The non-empty URL guard is what prevents a receipt from leaking
    onto a different or receipt-less expense: a bare (date, amount) collision
    is common (e.g. two same-day purchases of the same round amount), and only
    an expense that is itself known to own a receipt (non-empty receipt_url)
    is allowed to use that weaker match as a second attempt.
    """
    if not (receipt_url or '').strip():
        return None
    direct = deps.resolve_receipt_url_path(receipt_url)
    if direct:
        return direct
    by_da, _by_stem = deps.receipt_index()
    hits = by_da.get((date_str, amount_str)) if date_str and amount_str else None
    return hits[0] if hits else None


def receipt_url_for_path(deps: Collaborators, fp):
    """Build the dashboard URL that serves a receipt file, choosing the mount whose
    serve_base contains the file so external-store receipts get the right prefix."""
    ap = os.path.abspath(fp)
    for prefix, serve_base, _subtree in deps.receipt_mounts:
        base = os.path.abspath(serve_base)
        if os.path.commonpath([ap, base]) == base:
            rel = os.path.relpath(ap, base)
            return prefix + '/' + '/'.join(quote(part) for part in rel.split(os.sep))
    # Fallback: canonical mount (preserves prior behaviour for unexpected paths).
    rel = os.path.relpath(ap, os.path.abspath(deps.readable_docs_base))
    return deps.receipts_url_prefix + '/' + '/'.join(
        quote(part) for part in rel.split(os.sep))


def select_matching_expense(deps: Collaborators, rows, vendor_key, description):
    """Select one expense from same-date/same-amount candidates."""
    if not rows:
        return None
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
            chosen = rows[0]
    return chosen


def matching_expense(deps: Collaborators, cur, date_str, amount_str, vendor_key,
                     description, expense_id=None):
    """Return the expense matching a report row using the recategorization rules.

    Direct expense_id lookups must return that exact row, including LINE_ITEM
    children. Date/amount lookups intentionally remain parent-biased so report-row
    recategorization does not ambiguously land on an itemized sibling.
    """
    optional_columns = (
        'id_light', 'document_url', 'scanned_statement_url', 'moms_ledger',
        'notes', 'expense_role', 'parent_expense_id', 'address', 'map_link',
    )
    schema = ShowColumnsProbe().read(cur, optional_columns)
    select_sql = schema.select_clause(
        ('id', 'description', 'receipt_url', 'expense_date', 'amount'),
        optional_columns,
        quote='`',
    )
    role_filter = (
        " AND `expense_role` <> 'LINE_ITEM'" if schema.has('expense_role') else ''
    )
    if expense_id not in (None, ''):
        try:
            eid = int(expense_id)
        except (TypeError, ValueError):
            return None
        cur.execute(f"SELECT {select_sql} FROM expenses WHERE id=%s", (eid,))
        rows = cur.fetchall()
        return rows[0] if rows else None
    cur.execute(
        f"SELECT {select_sql} FROM expenses WHERE expense_date=%s AND amount=%s"
        f"{role_filter}", (date_str, amount_str)
    )
    return select_matching_expense(deps, cur.fetchall(), vendor_key, description)
