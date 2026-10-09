"""The pure scanner-intake lifecycle policy in scanner_state.py.

``intake_describes_current_scan`` is the backstop added after the 2026-10-09
outage, when the Letta server stopped answering, seven consecutive scans were
dropped with no intake record at all, and both scanner tabs kept rendering a
receipt from an hour earlier as though nothing had been scanned since.
"""

import time

from scanner_state import (
    intake_describes_current_scan,
    intake_is_in_progress,
)


def test_a_dispatch_after_the_scan_was_written_describes_it():
    scan_written = time.time()
    intake = {'dispatched_at': scan_written + 3}
    assert intake_describes_current_scan(intake, scan_written) is True


def test_a_dispatch_before_the_scan_was_written_cannot_describe_it():
    """The whole point: a newer page is sitting in the scanner's output file
    and this record predates it, so it is about some earlier document."""
    dispatched = time.time()
    scan_written_later = dispatched + 600
    intake = {'dispatched_at': dispatched}
    assert intake_describes_current_scan(intake, scan_written_later) is False


def test_rounding_jitter_does_not_read_as_a_newer_scan():
    dispatched = time.time()
    intake = {'dispatched_at': dispatched}
    assert intake_describes_current_scan(intake, dispatched + 0.4) is True


def test_no_output_file_leaves_a_good_record_alone():
    """Nothing proves the record is stale, and guessing 'stale' would hide a
    perfectly good report on a box whose scan output was cleaned up."""
    intake = {'dispatched_at': time.time()}
    assert intake_describes_current_scan(intake, None) is True


def test_a_record_with_no_dispatch_time_describes_nothing():
    assert intake_describes_current_scan({}, time.time()) is False
    assert intake_describes_current_scan({'dispatched_at': 0}, time.time()) is False
    assert intake_describes_current_scan({'dispatched_at': 'soon'}, time.time()) is False


def test_a_non_record_describes_nothing():
    assert intake_describes_current_scan(None, time.time()) is False
    assert intake_describes_current_scan('window_scan.jpg', time.time()) is False


def test_unreadable_mtime_leaves_the_record_alone():
    intake = {'dispatched_at': time.time()}
    assert intake_describes_current_scan(intake, 'yesterday') is True


def test_staleness_is_independent_of_in_progress():
    """The two policies answer different questions: one is 'may a new scan
    start', the other is 'is this report about the page now in the scanner'.
    A complete-but-stale intake is exactly the 2026-10-09 state."""
    dispatched = time.time() - 3600
    intake = {'status': 'complete', 'dispatched_at': dispatched}
    assert intake_is_in_progress(intake) is False
    assert intake_describes_current_scan(intake, time.time()) is False
