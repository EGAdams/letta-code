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
