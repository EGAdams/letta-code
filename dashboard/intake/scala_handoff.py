"""Leaving a non-financial scan to Scala instead of starting Mazda's turn.

Mazda's intake facade classifies every scan before her turn starts. For a
scanned JPEG its text-first router answers "unknown" by design -- receipts
included -- so "unknown" alone never skips her. The facade also reports what
the vision tier called the page (``vision_doc_type``), and when that is a kind
Mazda's finance checks do not cover (a tax form, anything "other"), with
confidence, her turn is skipped: she would only fail it.

The scan is still staged into ``incoming_scans/`` exactly as before, because
that copy is what Scala, the scanner clerk, watches and files. The intake is
recorded as complete with LEFT_FOR_SCALA as its detail, so the scanner tab
settles and the scan bridge can say it was out of Mazda's scope.

``DASHBOARD_SCALA_SKIPS_MAZDA=0`` turns the skip off; every scan then goes to
Mazda as it did before.
"""

from __future__ import annotations

import os

#: What the vision tier calls a page Mazda's finance checks do not apply to.
NON_FINANCIAL_VISION_TYPES = frozenset({'tax_document', 'other'})
MIN_VISION_CONFIDENCE = 0.80
LEFT_FOR_SCALA = ('Left for Scala: not a finance document (the vision check called it '
                  '{kind}), so Mazda\'s turn was skipped. Scala files it.')
LEFT_FOR_SCALA_PREFIX = 'Left for Scala:'


def skip_enabled() -> bool:
    return os.environ.get('DASHBOARD_SCALA_SKIPS_MAZDA', '1').strip() not in ('0', 'false', 'no', 'off')


def left_for_scala(facade, doc_kind_override=None) -> bool:
    """True only when the classifier itself said the page is not financial."""
    if doc_kind_override is not None or not skip_enabled():
        return False
    facade = facade or {}
    if not facade.get('ok') or facade.get('statement_preflight'):
        return False
    if (facade.get('doc_kind') or 'unknown') != 'unknown':
        return False
    kind = str(facade.get('vision_doc_type') or '').strip().lower()
    try:
        confidence = float(facade.get('vision_confidence') or 0)
    except (TypeError, ValueError):
        return False
    return kind in NON_FINANCIAL_VISION_TYPES and confidence >= MIN_VISION_CONFIDENCE


def leave_for_scala(deps, cfg, key, image_path, staged_path, facade, content_sha256):
    """Record the scan as handed to Scala and shape the inline result. No Mazda turn."""
    detail = LEFT_FOR_SCALA.format(kind=str(facade.get('vision_doc_type'))[:40])
    deps.record_recent_intake(
        staged_path, cfg.get('name', key), kind='scan', facade=facade,
        content_sha256=content_sha256, status='complete', status_detail=detail)
    result = deps.build_pipeline_result(facade, mazda_dispatched=False)
    result.update(trainer_dispatched=False, left_for_scala=True, note=detail,
                  execution_mode=deps.current_execution_mode(),
                  scanner=key, image_path=image_path)
    return result
