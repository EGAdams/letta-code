"""Mapping leaf `category_id` values to their reporting-bucket label/style.

Backs the Set Category dialog's palette, the picker's own name->id resolution,
and every report generator that needs to color a row by its rolled-up bucket
rather than its raw leaf category. ``get_category_taxonomy`` stays behind in
server.py -- it is the composition root for ICategoryTaxonomy, holding a
process-lifetime cache/lock -- so it arrives as a ``Collaborators`` field
built fresh per call, same reasoning as ``finance.recategorize.Collaborators``.

Not to be confused with ``finance.reporting_categories`` -- that module is the
typed bucket *registry* (``REPORTING_CATEGORY_CLASS`` and friends); this one is
the *lookup* logic server.py used to carry inline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_category_taxonomy: Callable
    reporting_category_class: dict
    reporting_category_db_map: dict


def reporting_category_for_id(deps: Collaborators, category_id, parent_of=None):
    """Walk a leaf category_id up its parent chain to a reporting-bucket name.

    Delegates to ICategoryTaxonomy, which sources the same walk from the DB's
    is_report_category / report_category_id columns. `parent_of` is retained
    for call-site compatibility and ignored: the taxonomy carries the parentage
    itself, so callers no longer need to pre-load the tree.
    """
    return deps.get_category_taxonomy().label_for(category_id)


def rol_finance_categories(deps: Collaborators):
    """The reporting-category palette (name/cls/bg/fg) in display order for the
    Set Category dialog. Sourced from ICategoryTaxonomy — i.e. from the
    `categories` table — so a category added by a migration shows up without a
    code change.

    /api/recategorize-expense resolves picks through the same taxonomy, so the
    picker still cannot offer a category the writer would reject.
    """
    cats = []
    for node in deps.get_category_taxonomy().selectable_report_categories():
        cats.append({
            'name': node.label,
            'cls': node.css_class or 'cat-uncategorized',
            'bg': node.report_bg or '#BFBFBF',
            'fg': node.report_fg or '#000000',
            'excluded': bool(node.excluded_from_nonprofit_totals),
        })
    # "Uncategorized" is a sentinel, not a row: picking it clears category_id.
    # Only append it when the taxonomy did not already supply it — LEGACY_TAXONOMY
    # (the offline fallback) lists it as selectable, and appending unconditionally
    # showed it twice in the dialog whenever the DB was unreachable.
    if not any(c['name'] == 'Uncategorized' for c in cats):
        cats.append({'name': 'Uncategorized', 'cls': 'cat-uncategorized',
                     'bg': '#BFBFBF', 'fg': '#000000', 'excluded': False})
    return cats


def rol_finance_category_for_ids(deps: Collaborators, category_ids):
    """Resolve raw (often leaf) `category_id` values to the reporting bucket
    they total under -- {name, cls, bg, fg} per id, keyed by the id as a string
    so the JSON round-trips cleanly.
    """
    taxonomy = deps.get_category_taxonomy()
    out = {}
    for raw_id in category_ids:
        try:
            cid = int(raw_id) if raw_id not in (None, '') else None
        except (TypeError, ValueError):
            cid = None
        style = taxonomy.style_for(cid)
        out[str(raw_id)] = {
            'name': taxonomy.label_for(cid),
            'cls': style.css_class,
            'bg': style.background,
            'fg': style.font,
        }
    return out


def report_category_node_by_name(deps: Collaborators, name, selectable_only=True):
    """Resolve a report/dialog label back to its category node.

    selectable_only=False also finds buckets the dialog does not offer — notably
    'Uncategorized' (node 1), which reports use as a label but which must never
    appear as a choice.
    """
    wanted = str(name or '').strip()
    taxonomy = deps.get_category_taxonomy()
    nodes = (taxonomy.selectable_report_categories() if selectable_only
             else [n for n in taxonomy.all_nodes() if n.is_report_category])
    for node in nodes:
        if node.label == wanted:
            return node
    return None


def css_class_for_report_name(deps: Collaborators, name):
    """The cat-* class for a reporting-bucket label, from the categories table.

    Reports bake this class into each <tr> on disk, so it must stay stable for
    existing buckets and must exist for new ones (a bucket with no class would
    render unstyled).
    """
    node = report_category_node_by_name(deps, name, selectable_only=False)
    if node is not None and node.css_class:
        return node.css_class
    return deps.reporting_category_class.get(name, 'cat-uncategorized')


def resolve_reporting_category(deps: Collaborators, name):
    """(target_category_id, css_class) for a dialog pick, or (None, None) if the
    name is not a selectable report category. 'Uncategorized' clears the id."""
    if str(name or '').strip() == 'Uncategorized':
        return None, 'cat-uncategorized'
    node = report_category_node_by_name(deps, name)
    if node is None:
        # Fall back to the legacy maps so a stale client (or a report.html
        # injected before this change) keeps working.
        if name in deps.reporting_category_db_map:
            return (deps.reporting_category_db_map[name],
                    deps.reporting_category_class.get(name, 'cat-uncategorized'))
        return None, None
    return node.id, (node.css_class or 'cat-uncategorized')


def account_number_in_label(label):
    """The 3-4 digit account number a report card's label is built around
    ('Bank 3119 PDF' -> '3119'), or None for a label with no such number."""
    m = re.search(r'\d{3,4}', label or '')
    return m.group(0) if m else None
