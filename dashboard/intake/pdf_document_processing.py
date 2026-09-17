"""Orchestrating the Process Document action for an existing PDF file, and
reprocessing a report's own source document.

Mirrors ``intake.document_processing.process_scanned_document`` but accepts an
absolute file path instead of a scanner key -- no staging is needed since a
PDF already lives inside ROL_FINANCES_DIR (enforced here), so executor_run on
this box reads it directly. ``reprocess_report`` calls
``deps.process_pdf_document`` (the server.py name, not this module's own
function) because tests monkeypatch it directly to drive reprocess_report
without a real dispatch -- same reasoning as
``intake.mazda_dispatch.Collaborators``.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

from health.document_vision import DOCUMENT_VISION_HALT_MESSAGE
from intake.mazda_dispatch import HUMAN_ONLY_MODE_STAGE_MESSAGE


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    rol_finances_dir: str
    run_intake_facade: Callable
    document_vision_health: Callable
    create_mazda_conversation: Callable
    record_recent_intake: Callable
    dispatch_mazda_or_block: Callable
    notify_mazda_of_pdf: Callable
    build_pipeline_result: Callable
    current_execution_mode: Callable
    source_document_path: Callable
    invalidate_receipt_index: Callable
    set_recent_report_pointer: Callable
    process_pdf_document: Callable


def process_pdf_document(deps: Collaborators, file_path, label=None, org_id=1,
                         engine='gemini'):
    """Orchestrate the Process Document action for an existing PDF file.

    Mirrors process_scanned_document but accepts an absolute file path instead
    of a scanner key. The path must resolve inside ROL_FINANCES_DIR.
    """
    try:
        real = os.path.realpath(os.path.expanduser(file_path))
        base = os.path.realpath(deps.rol_finances_dir)
        if not (real.startswith(base + os.sep) or real == base):
            return {'ok': False,
                    'error': 'File path must be inside the ROL finances directory.',
                    'stages': []}
    except Exception as exc:
        return {'ok': False, 'error': f'Invalid path: {exc}', 'stages': []}
    if not os.path.isfile(real):
        return {'ok': False, 'error': f'File not found: {file_path}', 'stages': []}
    facade = deps.run_intake_facade(real, org_id=org_id, engine=engine)
    doc_label = label or os.path.basename(real)
    vision_health = deps.document_vision_health()
    if not vision_health.get('ok'):
        result = deps.build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['vision_halted'] = True
        result['stage_error'] = DOCUMENT_VISION_HALT_MESSAGE
        result['file_path'] = real
        result['label'] = doc_label
        return result
    conversation_id = deps.create_mazda_conversation()
    if not conversation_id:
        result = deps.build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['stage_error'] = ('Could not create an isolated Mazda conversation; '
                                 'the PDF was not dispatched into shared context.')
        result['file_path'] = real
        result['label'] = doc_label
        return result
    dispatched_at = time.time()
    deps.record_recent_intake(real, doc_label, kind='pdf', facade=facade,
                              conversation_id=conversation_id,
                              dispatched_at=dispatched_at)
    # PDFs already live inside ROL_FINANCES_DIR (enforced above), so no staging
    # is needed — executor_run on this box reads them directly. This also
    # covers reprocess_report, which delegates here.
    mazda_dispatched = deps.dispatch_mazda_or_block(
        real, f'PDF intake ({doc_label})', facade, conversation_id, dispatched_at,
        deps.notify_mazda_of_pdf,
        (real, doc_label, conversation_id, dispatched_at, facade))
    result = deps.build_pipeline_result(facade, mazda_dispatched)
    result['trainer_dispatched'] = False
    result['execution_mode'] = deps.current_execution_mode()
    result['file_path'] = real
    result['label'] = doc_label
    result['conversation_id'] = conversation_id
    if not mazda_dispatched:
        result['stage_error'] = HUMAN_ONLY_MODE_STAGE_MESSAGE
    return result


def reprocess_report(deps: Collaborators, report_url):
    """Re-run the full intake pipeline (facade + Mazda) for a report's source document.

    Accepts the iframe URL of a report.html (e.g.
    /rol_finances_reports/jan-2025/fifth_third_non_profit_3119/report.html),
    resolves the source PDF/xlsx in the same directory, and delegates to
    process_pdf_document — which runs the deterministic facade inline and
    dispatches Mazda fire-and-forget for categorize→store→judge.
    """
    if not report_url:
        return {'ok': False, 'error': 'report_url is required.', 'stages': []}
    source_path = deps.source_document_path(report_url)
    if not source_path:
        return {
            'ok': False,
            'error': 'Could not resolve a source document (PDF/xlsx) for that report URL.',
            'stages': [],
        }
    if not os.path.isfile(source_path):
        return {
            'ok': False,
            'error': f'Source document not found on disk: {source_path}',
            'stages': [],
        }
    label = os.path.basename(os.path.dirname(source_path))
    # A reprocess can add/move receipt files; drop the index so the very next
    # receipts-present / Receipt-Only fetch reflects them without the 300s TTL wait.
    deps.invalidate_receipt_index()
    result = deps.process_pdf_document(source_path, label=label)
    # This document is now the most recently processed one — point
    # /recent_report.html at it regardless of how the pipeline run ends.
    # Set AFTER process_pdf_document so this report pointer is newer than the
    # intake record written inside it: a reprocessed document HAS a report.html
    # to show, so report mode must win the recency race.
    deps.set_recent_report_pointer(report_url)
    result['report_url'] = report_url
    return result
