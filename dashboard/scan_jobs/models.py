"""Boundary data for durable scan jobs (StrictModel: strict, frozen, extra='forbid').

A scan job is the one durable answer to "what did *this* scan produce?". The
scanner scripts overwrite `window_scan.jpg` / `scan_freezer.jpg` on every run,
so a job never points at those names after capture: it holds the sha256 of an
immutable copy in the artifact store, taken the moment the scan finished.

Hardware state (`status`) and Mazda's processing state (`mazda.status`) are
separate on purpose -- a scan can be captured perfectly and still have no
verdict yet, or never get one.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import ConfigDict, Field

from contracts import StrictModel

ScannerKey = Literal['window', 'freezer']
SCANNER_KEYS: tuple[str, ...] = ('window', 'freezer')

ScanStatus = Literal['queued', 'scanning', 'captured', 'failed', 'cancelled', 'timed_out', 'interrupted']
MazdaStatus = Literal['not_requested', 'pending', 'running', 'completed', 'failed', 'unavailable']
ScalaStatus = Literal['not_requested', 'pending', 'filed', 'inbox', 'handed_to_mazda', 'duplicate', 'error',
                      'unavailable']
ScanSource = Literal['dashboard', 'bridge']

ACTIVE_STATUSES: frozenset[str] = frozenset({'queued', 'scanning'})

#: The only moves a job may make. Everything not listed is terminal.
TRANSITIONS: dict[str, frozenset[str]] = {
    'queued': frozenset({'scanning', 'failed', 'cancelled', 'interrupted'}),
    'scanning': frozenset({'captured', 'failed', 'timed_out', 'interrupted'}),
}

SCAN_ID_RE = re.compile(r'^scan_[0-9A-HJKMNP-TV-Z]{26}$')
_CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def new_scan_id(now_ns: Optional[int] = None) -> str:
    """A sortable ULID-shaped id: 48 bits of milliseconds, 80 random bits."""
    ms = (now_ns if now_ns is not None else time.time_ns()) // 1_000_000
    value = (ms << 80) | int.from_bytes(os.urandom(10), 'big')
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return 'scan_' + ''.join(reversed(chars))


def rfc3339(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class ArtifactInfo(StrictModel):
    """The immutable bytes a scan produced. Resolved only through the store, by sha."""

    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    mime_type: Literal['image/jpeg', 'image/png', 'application/pdf']
    size_bytes: int = Field(ge=1)
    page_count: int = Field(ge=1)
    captured_at: str


class MazdaSummary(StrictModel):
    """Mazda's outcome for one scan, bounded and free of raw conversation text."""

    status: MazdaStatus = 'not_requested'
    outcome: Optional[str] = None          # the intake's own terminal word: pass, corrected, fail...
    doc_kind: Optional[str] = None
    vendor: Optional[str] = None
    detail: Optional[str] = Field(default=None, max_length=600)
    updated_at: Optional[str] = None
    warnings: tuple[str, ...] = ()


class ScalaSummary(StrictModel):
    """Scala's filing of one scan, read from her ledger by content hash. No paths, no document text."""

    status: ScalaStatus = 'not_requested'
    folder: Optional[str] = Field(default=None, max_length=120)    # her folder label, never a path
    method: Optional[str] = Field(default=None, max_length=40)     # rules, haiku, mazda_claim, ...
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason: Optional[str] = Field(default=None, max_length=400)    # read off the paper: untrusted
    updated_at: Optional[str] = None
    warnings: tuple[str, ...] = ()


class ScanRecord(StrictModel):
    scan_id: str = Field(pattern=SCAN_ID_RE.pattern)
    scanner: ScannerKey
    scanner_name: str
    source: ScanSource
    requester: str = Field(min_length=1, max_length=80)
    status: ScanStatus
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error: Optional[str] = Field(default=None, max_length=600)
    artifact: Optional[ArtifactInfo] = None
    mazda: MazdaSummary = MazdaSummary()

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def public(self, include_mazda_detail: bool = False) -> dict:
        """What the bridge may see. Mazda's detail needs scanner:verdict:read."""
        data = self.model_dump(mode='json')
        if not include_mazda_detail:
            data['mazda'] = {'status': self.mazda.status}
        return data


class RenderedPage(StrictModel):
    model_config = ConfigDict(**StrictModel.model_config, ser_json_bytes='base64', val_json_bytes='base64')

    page: int = Field(ge=1)
    rendition: Literal['preview', 'full']
    width: int
    height: int
    sha256: str
    jpeg: bytes


class PageText(StrictModel):
    page: int = Field(ge=1)
    text: str
    source: Literal['embedded_pdf_text', 'local_ocr', 'none']
    warnings: tuple[str, ...] = ()


class BridgeSettings(StrictModel):
    """~/.config/scan_bridge/settings.json, read on every start (no restart to toggle)."""

    bridge_start_enabled: bool = False
    min_seconds_between_bridge_scans: int = Field(default=60, ge=5)
    max_bridge_scans_per_hour: int = Field(default=12, ge=1, le=120)
    mazda_pending_window_seconds: int = Field(default=900, ge=60)
