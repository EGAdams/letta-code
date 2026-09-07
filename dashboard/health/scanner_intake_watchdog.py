"""Watchdog for a scanner intake Trainer was summoned for and then went dark on.

Found 2026-09-07 debugging a manual "Start Scan" that timed out with no
hardware process running anywhere. The scan request never reached the
scanner: `run_scanner()` in server.py refuses a new scan while
`_scanner_intake_in_progress()` says the previous document is still being
verified. That guard is correct in general, but nothing else in the system
supervises whether the Trainer run it is waiting on actually finishes.

The chain that broke: Mazda's callback reported no parsed/stored records, so
`ProblemOnlyTrainerEscalationService.observe()` (intake/trainer_escalation.py)
summoned a Trainer session and marked the intake `status: 'processing'`. That
escalation service only watches for the callback that SUMMONS Trainer — once
summoned, its job is done; it never checks whether Trainer itself completes.
Trainer's own watchdog loop (trainer/run_mazda_trainer.mjs) is supposed to
retry until it writes a report or an emergency report, but its process can
still die from outside (a killed systemd-run scope, a WSL VM restart, an OOM)
before either happens. When that occurs, the intake sits at
`status: 'processing'` with no report and no process, indefinitely — the only
thing that ever changes is `intake_is_in_progress()`'s 35-minute age ceiling
letting NEW scans through again, which unblocks the scanner but leaves the
stuck record, and the fact nobody was told, exactly as it was.

This tile makes that state visible on Server Management the moment it is
stale, instead of requiring an operator to hit a failed scan/test and go
spelunking through recent_report.json and /tmp/mazda_trainer_*.log by hand.
"""

from __future__ import annotations

import glob
import json
import os
import time

from health.probe import probe
from paths import HERE

RECENT_REPORT_PATH = os.path.join(HERE, 'recent_report.json')
TRAINER_REPORTS_DIR = os.path.join(HERE, 'trainer', 'reports')

# trainer/run_mazda_trainer.mjs budgets 35 minutes (TRAINER_TIMEOUT_MS) to
# either write a report or fall back to an emergency one. Every historical
# report in TRAINER_REPORTS_DIR resolved within a few minutes of dispatch.
# Padding past the full budget means "processing" with no report here means
# the Trainer process is gone, not merely slow.
STUCK_AFTER_SECONDS = 40 * 60


def _iter_scanner_intakes(pointer):
    scanner_intakes = pointer.get('scanner_intakes')
    if isinstance(scanner_intakes, dict):
        for label, intake in scanner_intakes.items():
            if isinstance(intake, dict):
                yield label, intake


def _has_matching_report(dispatched_at, conversation_id):
    """Best-effort: a report naming this dispatch second, or mentioning this
    conversation id anywhere in trainer/reports/. False negatives just mean a
    resolved intake gets flagged one poll late; false positives would hide a
    real stuck intake, so this never guesses in the other direction."""
    try:
        dispatch_second = int(float(dispatched_at))
    except (TypeError, ValueError):
        dispatch_second = None
    if dispatch_second is not None:
        pattern = os.path.join(TRAINER_REPORTS_DIR, f'*d{dispatch_second}*.md')
        if glob.glob(pattern):
            return True
    if not conversation_id:
        return False
    for path in glob.glob(os.path.join(TRAINER_REPORTS_DIR, '*.md')):
        try:
            with open(path) as f:
                if conversation_id in f.read():
                    return True
        except OSError:
            continue
    return False


def scanner_intake_watchdog_health(timeout=None):
    """Red when a scanner intake was handed to Trainer and never came back —
    no report, no completion callback — past the time a live Trainer session
    could plausibly still be running."""
    try:
        with open(RECENT_REPORT_PATH) as f:
            pointer = json.load(f)
    except FileNotFoundError:
        return probe(True, 'no scanner intakes recorded yet')
    except (OSError, json.JSONDecodeError) as e:
        return probe(False, f'cannot read {RECENT_REPORT_PATH}: {e}')

    now = time.time()
    stuck = []
    for label, intake in _iter_scanner_intakes(pointer):
        if str(intake.get('status') or '').lower() != 'processing':
            continue
        if not intake.get('trainer_dispatched'):
            continue
        try:
            age = now - float(intake.get('dispatched_at') or 0)
        except (TypeError, ValueError):
            continue
        if age < STUCK_AFTER_SECONDS:
            continue
        if _has_matching_report(intake.get('dispatched_at'),
                                 intake.get('conversation_id') or ''):
            continue
        stuck.append((label, age, intake))

    if not stuck:
        return probe(True, 'no stuck scanner intakes')

    details = '; '.join(
        f'{label} stuck {int(age / 60)}m, conversation '
        f'{intake.get("conversation_id", "?")}: {intake.get("status_detail", "")}'
        for label, age, intake in stuck
    )
    # `hard`: there is no process left to restart. The remedy is either
    # fixing whatever killed Trainer (see the module docstring) or, if the
    # document itself is unrecoverable, "Clear Verification Lock" on that
    # scanner's dialog.
    return probe(
        False,
        f'Trainer went dark on {len(stuck)} scanner intake(s) with no report '
        f'and no live process: {details}. New scans on the affected scanner '
        'stay blocked until the 35-minute age ceiling passes, or use '
        '"Clear Verification Lock".',
        hard=True,
    )
