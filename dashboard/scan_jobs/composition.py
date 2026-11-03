"""The one place scan_jobs names concretes and reaches into server.py.

Built lazily on first use (the dashboard's import order stays untouched) and
once per process; `reset()` exists for tests. `server` is imported late and
its attributes are read at call time, the same way http_app/registry.py does,
so tests' monkeypatches land.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from scan_jobs.artifact_store import FileArtifactStore
from scan_jobs.auth import TokenAuthorizer
from scan_jobs.document_reader import LocalDocumentReader
from scan_jobs.mazda_verdicts import IntakeMazdaVerdicts
from scan_jobs.repository import SqliteScanJobRepository
from scan_jobs.scala_filings import LedgerScalaFilings
from scan_jobs.service import ScanJobService, load_settings

log = logging.getLogger('scan_jobs')

_lock = threading.Lock()
_built: Optional[tuple[ScanJobService, TokenAuthorizer, SqliteScanJobRepository]] = None
_filings: Optional[LedgerScalaFilings] = None


def data_dir() -> Path:
    return Path(os.environ.get('SCAN_JOBS_DIR') or Path.home() / '.local/share/scan_jobs')


def config_dir() -> Path:
    return Path(os.environ.get('SCAN_BRIDGE_CONFIG_DIR') or Path.home() / '.config/scan_bridge')


def _server():
    return sys.modules.get('server') or importlib.import_module('server')


class ServerScannerController:
    """IScannerController over the dashboard's existing, locked scan path."""

    def run(self, key: str) -> dict:
        return _server().run_scanner(key)

    def output_path(self, key: str) -> Optional[str]:
        from hardware import scanners
        path = scanners.image_path(key, _server().SCAN_TOOLS_DIR)
        return str(path) if path else None

    def scanner_name(self, key: str) -> str:
        spec = _server().SCANNERS.get(key) or {}
        return str(spec.get('name') or key)


def _intake_lookup(scanner_key: str) -> Optional[dict]:
    intake = _server().get_scanner_intake(scanner_key)
    return intake if isinstance(intake, dict) else None


def _build() -> tuple[ScanJobService, TokenAuthorizer, SqliteScanJobRepository]:
    root, config = data_dir(), config_dir()
    settings_file = config / 'settings.json'
    repo = SqliteScanJobRepository(root / 'scan_jobs.sqlite3')
    recovered = repo.interrupt_active()
    if recovered:
        log.warning('marked %d unfinished scan job(s) interrupted after restart', recovered)
    verdicts = IntakeMazdaVerdicts(_intake_lookup,
                                   pending_window_seconds=load_settings(settings_file).mazda_pending_window_seconds)
    service = ScanJobService(repo, FileArtifactStore(root / 'artifacts'), ServerScannerController(),
                             LocalDocumentReader(), verdicts, lambda: load_settings(settings_file))
    return service, TokenAuthorizer(config / 'clients.json'), repo


def _get() -> tuple[ScanJobService, TokenAuthorizer, SqliteScanJobRepository]:
    global _built
    with _lock:
        if _built is None:
            _built = _build()
        return _built


def service() -> ScanJobService:
    return _get()[0]


def authorizer() -> TokenAuthorizer:
    return _get()[1]


def scala_home() -> Path:
    return Path(os.environ.get('SCALA_HOME') or Path.home() / 'scala')


def filings() -> LedgerScalaFilings:
    """Scala's ledger (her own SCALA_HOME convention), read-only."""
    global _filings
    with _lock:
        if _filings is None:
            _filings = LedgerScalaFilings(scala_home() / 'ledger.jsonl')
        return _filings


def audit(scan_id: Optional[str], actor: str, event: str, detail: str = '') -> None:
    try:
        _get()[2].audit(scan_id, actor, event, detail)
    except Exception:  # noqa: BLE001 -- an audit write never fails a read
        log.exception('scan audit write failed')


def reset() -> None:
    global _built, _filings
    with _lock:
        _built = None
        _filings = None
