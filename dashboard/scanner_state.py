"""Pure lifecycle policy for scanner intake records."""

import time


def intake_is_in_progress(intake, max_age_seconds=35 * 60):
    """Return whether a persisted scanner intake still owns the scanner."""
    if not isinstance(intake, dict):
        return False
    if str(intake.get('status') or '').lower() != 'processing':
        return False
    try:
        age = time.time() - float(intake.get('dispatched_at') or 0)
    except (TypeError, ValueError):
        return False
    return 0 <= age < max_age_seconds


def intake_describes_current_scan(intake, scan_output_mtime, grace_seconds=1.0):
    """Return whether a recorded intake describes the image now in the
    scanner's output file.

    The backstop for the 2026-10-09 "both scanner tabs show an older scan"
    failure. Every branch of ``process_scanned_document`` that gives up on a
    document is *supposed* to record a terminal intake against its scanner --
    the blank-page rejection says why in its own comment: a scan that is
    dropped without a record reads as a stuck scanner still showing the
    previous document. Two branches did not (staging failure and
    conversation-creation failure), so when the Letta server stopped answering,
    seven scans in a row vanished and both tabs kept rendering 14:46.

    Those branches are fixed, but "every future branch remembers to record"
    is not an invariant anything enforces. This one is checkable from outside:
    the scanner's output file is the physical truth about what was last
    scanned, and an intake dispatched BEFORE that file was written cannot be
    about it. The report view asks this before rendering, so a missing record
    shows as "this scan was never recorded" rather than as last hour's receipt.

    ``grace_seconds`` absorbs clock/mtime rounding only -- dispatch always
    happens strictly after the scan is written, by seconds, never before.
    """
    if not isinstance(intake, dict):
        return False
    try:
        dispatched_at = float(intake.get('dispatched_at') or 0)
    except (TypeError, ValueError):
        return False
    if dispatched_at <= 0:
        return False
    if scan_output_mtime is None:
        # No output file to compare against (a fresh box, or a scanner whose
        # output was cleaned up). Nothing proves the record is stale, and
        # guessing "stale" would hide a perfectly good report.
        return True
    try:
        mtime = float(scan_output_mtime)
    except (TypeError, ValueError):
        return True
    return mtime <= dispatched_at + grace_seconds
