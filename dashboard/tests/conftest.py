"""Make the dashboard package importable from tests (so `import voice` works)."""
import os
import sys

import pytest

DASHBOARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)


@pytest.fixture(autouse=True)
def _isolate_intake_side_effects(tmp_path, monkeypatch):
    """Keep intake-pipeline tests from leaking into the live dashboard.

    - RECENT_REPORT_POINTER_FILE: process_scanned_document/process_pdf_document
      write an intake record; without isolation a pytest run overwrites the
      LIVE recent_report.json and /recent_report.html shows a phantom test
      intake.
    - TRAINER_ENABLED: tests that don't mock _notify_trainer_of_scan would
      spawn a REAL Trainer agent (a paid ~25-minute Claude session) per run —
      this happened on 2026-07-12: a pytest run's trainer ("Window Scanner",
      the test's fake staged path) polled Mazda for 16 minutes and filed a
      misleading STALLED report for a scan that never existed.
    - _scan_dispatch_claims: the one-dispatch-per-image guard is module state;
      clear it so tests never inherit a claim from an earlier test.
    - _create_mazda_conversation: intake tests must not create live Letta
      conversations unless they explicitly replace this stub.
    - SCAN_ARCHIVE_ROOT/SCAN_ARCHIVE_INDEX_PATH: archive_scan_permanently()
      runs unconditionally inside process_scanned_document; without isolation
      a pytest run writes real files + index entries into the LIVE permanent
      scan archive under ~/rol_finances (found 2026-07-21 during the archive
      feature's own test run — three tiny test-fixture files landed in the
      real archive directory).
    """
    import server
    monkeypatch.setattr(
        server, 'RECENT_REPORT_POINTER_FILE',
        str(tmp_path / 'recent_report_pointer.json'))
    monkeypatch.setattr(server, 'TRAINER_ENABLED', False)
    monkeypatch.setattr(server, '_create_mazda_conversation',
                        lambda: 'conv-test-isolated')
    monkeypatch.setattr(server, 'SCAN_ARCHIVE_ROOT', str(tmp_path / 'scan_archive'))
    monkeypatch.setattr(server, 'SCAN_ARCHIVE_INDEX_PATH',
                        str(tmp_path / 'scan_archive' / 'index.json'))
    server._scan_dispatch_claims.clear()
    yield
    server._scan_dispatch_claims.clear()
