"""Shared fakes for the scan_jobs tests: a scanner that overwrites one file per
key (like the real scripts do), a controllable clock, and image/PDF makers."""

from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Callable, Optional

from scan_jobs.artifact_store import FileArtifactStore
from scan_jobs.document_reader import LocalDocumentReader
from scan_jobs.mazda_verdicts import IntakeMazdaVerdicts
from scan_jobs.models import BridgeSettings
from scan_jobs.repository import SqliteScanJobRepository
from scan_jobs.service import ScanJobService


def jpeg(color: tuple[int, int, int], size: tuple[int, int] = (300, 400)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'JPEG', quality=90)
    return buf.getvalue()


def png(color: tuple[int, int, int], size: tuple[int, int] = (200, 100)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    return buf.getvalue()


def pdf(pages: list[str]) -> bytes:
    import fitz
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


class Clock:
    def __init__(self) -> None:
        self.now = time.time_ns()

    def __call__(self) -> int:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += int(seconds * 10**9)


class FakeScanner:
    """Writes `next_bytes[key]` over the one output file per key, like the scripts."""

    def __init__(self, root: Path, clock: Clock) -> None:
        self.root, self.clock = Path(root), clock
        self.calls: list[str] = []
        self.next_bytes: dict[str, bytes] = {}
        self.next_result: dict[str, dict] = {}
        self.touch = True
        self.root.mkdir(parents=True, exist_ok=True)

    def output_path(self, key: str) -> Optional[str]:
        return str(self.root / f'{key}_scan.jpg')

    def scanner_name(self, key: str) -> str:
        return {'window': 'Window Scanner', 'freezer': 'Freezer Scanner'}.get(key, key)

    def run(self, key: str) -> dict:
        self.calls.append(key)
        result = self.next_result.pop(key, None)
        if result is not None:
            return result
        path = self.output_path(key)
        if self.touch:
            with open(path, 'wb') as out:
                out.write(self.next_bytes.get(key) or jpeg((10, 20, 30)))
            os.utime(path, ns=(self.clock(), self.clock()))
        return {'status': 'ready', 'ok': True, 'image_url': f'/scan/{key}'}


class Rig:
    """A ScanJobService over real storage in tmp_path and the fake scanner."""

    def __init__(self, tmp_path: Path, enabled: bool = True,
                 intake: Optional[Callable[[str], Optional[dict]]] = None,
                 spawn: Optional[Callable] = None) -> None:
        self.clock = Clock()
        self.scanner = FakeScanner(tmp_path / 'scan_tools', self.clock)
        self.settings = BridgeSettings(bridge_start_enabled=enabled)
        self.intakes: dict[str, dict] = {}
        self.repo = SqliteScanJobRepository(tmp_path / 'jobs' / 'scan_jobs.sqlite3', clock_ns=self.clock)
        self.store = FileArtifactStore(tmp_path / 'jobs' / 'artifacts')
        verdicts = IntakeMazdaVerdicts(intake or self.intakes.get, clock_ns=self.clock)
        self.pending: list[Callable[[], None]] = []
        self.service = ScanJobService(self.repo, self.store, self.scanner, LocalDocumentReader(ocr=lambda _: 'OCR TEXT', orientation=lambda _: 0),
                                      verdicts, lambda: self.settings, clock_ns=self.clock,
                                      spawn=spawn or (lambda fn: fn()))
