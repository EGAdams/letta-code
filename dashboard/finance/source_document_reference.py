"""Choosing the source-document reference to offer for one expense row.

The stored `document_url` wins, but only while it still resolves and while it
is not simply a duplicate of the row's own receipt or scanned-statement slot
(see `supporting_document_service.should_suppress_source_document` /
`references_same_underlying_document`, the shared de-duplication rules every
supporting-document slot uses).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from supporting_document_service import (
    references_same_underlying_document,
    should_suppress_source_document,
)


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    resolve_local_supporting_document: Callable
    report_scanned_statement_reference: Callable
    usable_document_reference: Callable
    report_source_document_reference: Callable
    find_matching_report_row: Callable
    source_document_path: Callable


def source_document_reference(deps: Collaborators, chosen, report_path=''):
    """The source-document reference to offer for one expense row.

    The stored `document_url` wins, but only while it still resolves. A scan
    image that disappears after storage (2026-07-29: a concurrent agent's
    `git add -A` swept two in-flight scans off disk) otherwise left the dialog
    with no View Source Document button at all, even on a scanner report that
    knows exactly which image it came from.
    """
    chosen = chosen or {}
    reference = chosen.get('document_url') or ''
    reference = str(reference).strip()
    receipt_reference = str(chosen.get('receipt_url') or '').strip()
    if should_suppress_source_document(
            reference,
            receipt_reference,
            resolve_local_path=lambda ref: deps.resolve_local_supporting_document(
                ref, 'source'
            ) or deps.resolve_local_supporting_document(ref, 'receipt')):
        return ''
    scanned_statement_reference = str(
        chosen.get('scanned_statement_url') or '').strip()
    if not scanned_statement_reference:
        scanned_statement_reference = deps.report_scanned_statement_reference(report_path)

    # Resolve the effective source candidate before comparing it with the
    # scanned statement.  The old order only compared the stored
    # ``document_url``; when that field was empty, the report-directory
    # fallback could resolve to the exact same JPG and expose two buttons for
    # one document.
    source_reference = reference
    if not (deps.usable_document_reference(source_reference) and (
            urlparse(source_reference).scheme in {'http', 'https'}
            or deps.resolve_local_supporting_document(source_reference, 'source'))):
        source_reference = deps.report_source_document_reference(report_path) or ''

    if not source_reference:
        # Scanner and Recent-Report intake pages are synthetic - they have no
        # report.html of their own, so report_source_document_reference always
        # comes back empty for them (see SupportingDocumentPageResolver). But
        # the row's own (date, amount) may still match an existing month
        # report's transaction row - the exact match associated_source_paths
        # already uses to print "Associated PDF" on the intake page header.
        # Reuse it here instead of leaving a real downloaded statement
        # undiscoverable just because this row surfaced via a scan.
        match = deps.find_matching_report_row(
            str(chosen.get('expense_date') or ''),
            str(chosen.get('amount') or ''))
        if match:
            source_reference = deps.source_document_path(match.report_path) or ''

    if references_same_underlying_document(
            source_reference,
            scanned_statement_reference,
            resolve_local_path=lambda ref: (
                deps.resolve_local_supporting_document(ref, 'source')
                or deps.resolve_local_supporting_document(ref, 'scanned_statement')
            )):
        return ''
    if deps.usable_document_reference(source_reference) and (
            urlparse(source_reference).scheme in {'http', 'https'}
            or deps.resolve_local_supporting_document(source_reference, 'source')):
        return source_reference
    # A stale stored path is not evidence.  In particular, never return a
    # missing scanner image as a downloaded source document; the scanner page's
    # paper copy is resolved through the separate scanned-statement slot.
    return ''
