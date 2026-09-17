"""Manual scan control: kick off a scan, read its state, clear a stuck lock.

``scanner_intake_in_progress`` is individually monkeypatched by many tests to
drive the other three functions through their branches without a real
intake record, so internal calls route through ``deps.scanner_intake_in_progress``
(the server.py name) rather than this module's own function -- same reasoning
as ``intake.mazda_dispatch.Collaborators``. The background dispatch thread is
started via the bare ``threading`` module (not ``from threading import
Thread``) so ``monkeypatch.setattr(server.threading, 'Thread', fake)`` is
still honoured, and its target is ``deps.process_scanned_document`` itself
(not a wrapper) so a test asserting the exact function object still passes.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

from scanner_state import intake_is_in_progress


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    scanners: dict
    scan_tools_dir: str
    get_scanner_intake: Callable
    scanner_intake_in_progress: Callable
    invoke_scanner: Callable
    record_recent_intake: Callable
    process_scanned_document: Callable
    merge_recent_intake_status: Callable
    scan_lock: object
    scanner_runtime_status: dict
    scanner_runtime_status_lock: object


def scanner_intake_in_progress(deps: Collaborators, key, max_age_seconds=35 * 60):
    return intake_is_in_progress(
        deps.get_scanner_intake(key), max_age_seconds=max_age_seconds)


def run_scanner(deps: Collaborators, key):
    """Manual scan (POST /api/scanner-scan). Adds back-compat `ok` to the status.

    When the scan finishes ready, the SERVER dispatches the intake pipeline in a
    background thread. The frontend still POSTs /api/process-document for its
    inline stage display, but that call no longer carries the dispatch: on
    2026-07-12 a scan's intake was lost because dispatch relied on the browser
    surviving the scan. claim_scan_dispatch keeps the two paths from ever
    double-dispatching Mazda for the same image.
    """
    if deps.scanner_intake_in_progress(key):
        return {
            'ok': False,
            'status': 'intake_busy',
            'error': ('The previous document from this scanner is still being '
                      'verified. Wait for its Trainer PASS/FAIL before scanning another.'),
        }
    result = deps.invoke_scanner(key)
    result['ok'] = (result.get('status') == 'ready')
    if result.get('empty_output'):
        # Nothing was dispatched, so no STEP 8 callback is ever coming. Record
        # the failure against this scanner ourselves -- same reason as the
        # blank-page rejection in process_scanned_document.
        deps.record_recent_intake(
            os.path.join(deps.scan_tools_dir, (deps.scanners.get(key) or {}).get('output', '')),
            (deps.scanners.get(key) or {}).get('name'),
            status='fail', status_detail=result.get('error') or '')
    with deps.scanner_runtime_status_lock:
        # Keep compatibility for code that inspects this runtime map, but GET
        # derives live state from intake and lock ownership. In particular, a
        # physical-attempt busy/offline failure remains in this POST response
        # only and cannot leave status indefinitely wedged.
        deps.scanner_runtime_status[key] = {'status': 'idle', 'ok': True}
    if result['ok']:
        threading.Thread(
            target=deps.process_scanned_document, args=(key,), daemon=True,
        ).start()
    return result


def scanner_status(deps: Collaborators, key):
    """Read-only scanner state. Never starts WIA or writes a scan image."""
    if key not in deps.scanners:
        return {'status': 'error', 'ok': False, 'error': f'Unknown scanner: {key}'}
    if deps.scanner_intake_in_progress(key):
        return {
            'status': 'intake_busy',
            'ok': False,
            'error': ('The previous document from this scanner is still being '
                      'verified. Wait for intake completion or a problem-triggered '
                      'Trainer verdict before scanning another.'),
        }
    if deps.scan_lock.locked():
        return {
            'status': 'busy',
            'ok': False,
            'error': 'A scanner transfer is currently in progress.',
        }
    return {'status': 'idle', 'ok': True}


def clear_scanner_verification_lock(deps: Collaborators, key):
    """Terminal-out one scanner's stuck intake lock without changing finance data."""
    if key not in deps.scanners:
        return {'ok': False, 'error': f'Unknown scanner: {key}'}
    intake = deps.get_scanner_intake(key)
    if not intake or not deps.scanner_intake_in_progress(key):
        return {'ok': True, 'cleared': False,
                'message': 'No active verification lock was found.'}
    update = {
        'conversation_id': intake.get('conversation_id'),
        'document_path': intake.get('image_path'),
        'dispatched_at': intake.get('dispatched_at'),
        'status': 'stalled',
        'detail': ('Verification lock cleared manually from the scanner view; '
                   'the scan and financial records were left unchanged.'),
    }
    if not deps.merge_recent_intake_status(update):
        return {'ok': False, 'error': 'The active verification lock could not be matched.'}
    with deps.scanner_runtime_status_lock:
        deps.scanner_runtime_status[key] = {'status': 'idle', 'ok': True}
    return {'ok': True, 'cleared': True, 'status': 'idle'}
