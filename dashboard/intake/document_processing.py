"""Orchestrating the Process Document action for one scanner's latest image.

``process_scanned_document`` is intake's top-level composition: resolve the
scanner's output image, run the deterministic facade (classify + parse) for
the inline result, and dispatch Mazda fire-and-forget for investigate ->
categorize -> store. No polling: the deeper stages run in Mazda's own time
and surface in her own agent transcript, not here.

Nearly everything this function touches arrives as a ``Collaborators`` bundle
built fresh per call (never captured at import), same reasoning as
``intake.mazda_dispatch.Collaborators`` -- and for the same two reasons that
module gives: some of it (the scan lock, the dedupe/claim bookkeeping,
conversation creation, the Mazda-or-block fork) genuinely IS shared,
in-process state that has to keep living in server.py. The rest (`SCANNERS`,
`SCAN_TOOLS_DIR`, `document_vision_health`, `inspect_scan_image_quality`,
`run_statement_preflight`, `run_intake_facade`) has an owning module of its
own, but ``tests/test_server.py`` monkeypatches every one of them by its
`server.` name to drive this function through its branches without a real
scanner, a real vision provider, or a real statement parse -- so those, too,
have to be read through server.py's name at call time rather than imported
here directly, or the patch lands on a name nothing calls any more. Only
`_scan_output_ready` (pure, stateless, never faked in a test) is imported
straight from its owning module.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

from hardware.scan_result import _scan_output_ready
from health.document_vision import DOCUMENT_VISION_HALT_MESSAGE
from intake.mazda_dispatch import HUMAN_ONLY_MODE_STAGE_MESSAGE

STATEMENT_DOC_KINDS = ('statement', 'bank_statement')


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    scanners: dict
    scan_tools_dir: str
    scan_locked: Callable
    record_recent_intake: Callable
    human_override_facade: Callable
    run_intake_facade: Callable
    document_vision_health: Callable
    inspect_scan_image_quality: Callable
    run_statement_preflight: Callable
    build_pipeline_result: Callable
    scan_content_sha256: Callable
    claim_scan_dispatch: Callable
    stage_scan_for_mazda: Callable
    write_statement_preflight_payload: Callable
    create_mazda_conversation: Callable
    dispatch_mazda_or_block: Callable
    notify_mazda_of_scan_and_record_failure: Callable
    release_scan_dispatch: Callable
    current_execution_mode: Callable


def process_scanned_document(
        deps: Collaborators, key, org_id=1, engine='gemini',
        statement_metadata=None, doc_kind_override=None):
    """Orchestrate the Process Document action for one scanner's latest image.

    1. Resolve the scanner's output image.
    2. Run the deterministic facade (classify + parse) for the inline result
       -- or, when `doc_kind_override` names a statement kind, skip that paid
       classify call and use the operator's own assertion instead (see
       deps.human_override_facade).
    3. Dispatch Mazda fire-and-forget for investigate → categorize → store.
    No polling: the deeper stages run in Mazda's own time and surface in her
    own agent transcript, not here.
    """
    cfg = deps.scanners.get(key)
    if not cfg:
        return {'ok': False, 'error': f'Unknown scanner: {key}', 'stages': []}
    image_path = os.path.join(deps.scan_tools_dir, cfg.get('output', ''))
    if deps.scan_locked():
        return {
            'ok': False,
            'error': 'The scanner is still scanning. Processing will start when the image is complete.',
            'stage_error': 'Scanner transfer still in progress.',
            'scanner': key,
            'image_path': image_path,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    if not _scan_output_ready(image_path):
        return {
            'ok': False,
            'error': 'The scanner did not produce a usable image. Please scan the document again.',
            'stage_error': 'The scanner output image is missing or empty.',
            'scanner': key,
            'image_path': image_path,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    image_quality = deps.inspect_scan_image_quality(image_path)
    if not image_quality.get('ok'):
        # Before the facade, before vision health, before Mazda: a page with
        # nothing on it cannot become an expense, and every stage past here
        # costs either an API call or an agent's turn. Recorded as this
        # scanner's own last intake so the rejection is visible on its tab --
        # otherwise a failed capture reads as a stuck scanner still showing
        # the previous document.
        reason = image_quality.get('reason') or 'The scan is not readable.'
        deps.record_recent_intake(image_path, cfg.get('name'), status='fail',
                                  status_detail=reason)
        return {
            'ok': False,
            'error': reason,
            'stage_error': reason,
            'scanner': key,
            'image_path': image_path,
            'image_quality': image_quality,
            'mazda_dispatched': False,
            'trainer_dispatched': False,
            'stages': [],
        }
    if doc_kind_override is not None:
        if doc_kind_override not in STATEMENT_DOC_KINDS:
            return {
                'ok': False,
                'error': f'Unsupported doc_kind_override: {doc_kind_override}',
                'scanner': key, 'image_path': image_path,
                'mazda_dispatched': False, 'trainer_dispatched': False,
                'stages': [],
            }
        facade = deps.human_override_facade(doc_kind_override)
    else:
        facade = deps.run_intake_facade(image_path, org_id=org_id, engine=engine)
    mazda_dispatched = False
    trainer_dispatched = False
    stage_error = None
    conversation_id = None
    vision_health = deps.document_vision_health()
    if not vision_health.get('ok'):
        # All 3 classify_scan.py vision tiers are down -- dispatching Mazda would
        # just strand her mid-trace with nothing that can read the image (see
        # DOCUMENT_VISION_HALT_MESSAGE). Halt here instead: /api/server-health
        # already reports 'document-vision' red for the same reason, and the
        # frontend's VisionHaltAlert modal/tab-red state is driven by that,
        # not by this response.
        result = deps.build_pipeline_result(facade, mazda_dispatched=False)
        result['trainer_dispatched'] = False
        result['vision_halted'] = True
        result['stage_error'] = DOCUMENT_VISION_HALT_MESSAGE
        result['scanner'] = key
        result['image_path'] = image_path
        return result
    statement_preflight = deps.run_statement_preflight(
        image_path, facade, metadata=statement_metadata)
    if statement_preflight is not None:
        if not statement_preflight.get('ok'):
            result = deps.build_pipeline_result(facade, mazda_dispatched=False)
            result['trainer_dispatched'] = False
            result['scanner'] = key
            result['image_path'] = image_path
            result['stage_error'] = statement_preflight.get('error')
            result['needs_statement_metadata'] = bool(
                statement_preflight.get('needs_statement_metadata'))
            result['statement_rejected'] = bool(statement_preflight.get('rejected'))
            result['missing_fields'] = statement_preflight.get('missing_fields', [])
            result['statement_metadata'] = {
                'bank_name': statement_preflight.get('bank_name'),
                'account_last4': statement_preflight.get('account_last4'),
            }
            return result
        facade = dict(facade)
        facade['statement_preflight'] = statement_preflight
        facade['vendor'] = statement_preflight['bank_name']
    if os.path.isfile(image_path):
        content_sha256 = deps.scan_content_sha256(image_path)
        if not deps.claim_scan_dispatch(key, image_path, content_sha256):
            # This exact image was already dispatched (the server auto-fires
            # intake when a scan finishes AND the frontend still POSTs
            # /api/process-document) -- never send Mazda the same document twice.
            result = deps.build_pipeline_result(facade, mazda_dispatched=True)
            result['trainer_dispatched'] = False
            result['already_dispatched'] = True
            result['scanner'] = key
            result['image_path'] = image_path
            return result
        remote_image_path = deps.stage_scan_for_mazda(image_path)
        if remote_image_path:
            if facade.get('statement_preflight'):
                payload_path = deps.write_statement_preflight_payload(
                    remote_image_path, facade['statement_preflight'])
                if payload_path:
                    facade = dict(facade)
                    facade['statement_preflight'] = dict(
                        facade['statement_preflight'], payload_path=payload_path)
            conversation_id = deps.create_mazda_conversation()
            if conversation_id:
                dispatched_at = time.time()
                # Persist first: a fast transport failure in the worker must
                # have an exact intake record to mark terminal.
                deps.record_recent_intake(
                    remote_image_path, cfg.get('name', key), kind='scan',
                    facade=facade, conversation_id=conversation_id,
                    dispatched_at=dispatched_at,
                    content_sha256=content_sha256)
                mazda_dispatched = deps.dispatch_mazda_or_block(
                    remote_image_path, cfg.get('name', key), facade,
                    conversation_id, dispatched_at,
                    deps.notify_mazda_of_scan_and_record_failure,
                    (remote_image_path, cfg.get('name', key), facade,
                     conversation_id, dispatched_at))
                if not mazda_dispatched:
                    stage_error = HUMAN_ONLY_MODE_STAGE_MESSAGE
            else:
                deps.release_scan_dispatch(key, image_path)
                stage_error = ('Could not create an isolated Mazda conversation; '
                               'the scan was not dispatched into shared context.')
        else:
            deps.release_scan_dispatch(key, image_path)
            stage_error = ('Could not copy the scan to where Mazda can read it '
                            '(SSH/copy to the executor machine failed) — Mazda was not notified.')
    result = deps.build_pipeline_result(facade, mazda_dispatched)
    result['trainer_dispatched'] = trainer_dispatched
    result['execution_mode'] = deps.current_execution_mode()
    if conversation_id:
        result['conversation_id'] = conversation_id
    if stage_error:
        result['stage_error'] = stage_error
    result['scanner'] = key
    result['image_path'] = image_path
    return result
