"""Rebuild problem-only Trainer watches from persisted intake state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from intake.trainer_contracts import ITrainerEscalationService, TrainerLaunchRequest


def recover_pending_trainer_watches(
    pointer: Mapping[str, Any], service: ITrainerEscalationService
) -> int:
    candidates = [pointer.get('intake')]
    scanner_intakes = pointer.get('scanner_intakes')
    if isinstance(scanner_intakes, Mapping):
        candidates.extend(scanner_intakes.values())

    recovered = 0
    seen: set[tuple[str, int]] = set()
    for intake in candidates:
        if not isinstance(intake, Mapping):
            continue
        if str(intake.get('status') or '').lower() != 'processing':
            continue
        if intake.get('trainer_dispatched') is True:
            continue
        try:
            request = TrainerLaunchRequest(
                scan_path=str(intake.get('image_path') or ''),
                scanner_name=str(intake.get('label') or 'Document intake'),
                facade_result={
                    'doc_kind': intake.get('doc_kind') or 'unknown',
                    'vendor': intake.get('vendor') or 'unknown',
                },
                conversation_id=str(intake.get('conversation_id') or ''),
                dispatched_at=float(intake.get('dispatched_at') or 0),
            )
        except (TypeError, ValueError, ValidationError):
            continue
        if request.correlation_key in seen:
            continue
        seen.add(request.correlation_key)
        if service.watch(request):
            recovered += 1
    return recovered
