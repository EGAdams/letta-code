"""Persistence for finished-run token samples.

Small, append-mostly, and read by an HTTP handler on every poll, so it is a
single JSON file rewritten atomically rather than a database. The interesting
requirement is idempotency: the sampler re-observes the same finished run for
as long as its status event stays in the executor's 400-event buffer, and a
second write of the same run_id would double the reported rate.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional

from pydantic import ValidationError

from health.claude_sdk_usage_contracts import (
    IRunUsageStore,
    RunUsageSample,
    prune,
)


class JsonFileRunUsageStore(IRunUsageStore):
    """One JSON file beside the other small dashboard state.

    A corrupt or missing file means "no history", never an exception at the
    caller: losing the rate history is a cosmetic loss, while a raise here
    would take out the Server Management page that displays it.
    """

    def __init__(self, path: str, clock=time.time):
        self._path = path
        self._clock = clock
        self._lock = threading.Lock()

    def record(self, sample: RunUsageSample) -> bool:
        with self._lock:
            existing = self._read_unlocked()
            if any(known.run_id == sample.run_id for known in existing):
                return False
            self._write_unlocked(prune([*existing, sample], self._clock()))
            return True

    def samples(self) -> List[RunUsageSample]:
        with self._lock:
            return prune(self._read_unlocked(), self._clock())

    def _read_unlocked(self) -> List[RunUsageSample]:
        try:
            with open(self._path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        rows = data.get('samples') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []
        samples = []
        for row in rows:
            try:
                samples.append(RunUsageSample.model_validate(row))
            except ValidationError:
                continue
        return samples

    def _write_unlocked(self, samples: List[RunUsageSample]) -> None:
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {'samples': [s.model_dump(mode='json') for s in samples]}
        tmp = f'{self._path}.tmp.{os.getpid()}'
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle)
            os.replace(tmp, self._path)
        except OSError:
            # Same reasoning as the read: an unwritable state file must not
            # take down the page it decorates.
            pass


class InMemoryRunUsageStore(IRunUsageStore):
    """For tests, and for a box that would rather not keep the history."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._samples: Dict[str, RunUsageSample] = {}
        self._lock = threading.Lock()

    def record(self, sample: RunUsageSample) -> bool:
        with self._lock:
            if sample.run_id in self._samples:
                return False
            self._samples[sample.run_id] = sample
            keep = {s.run_id for s in prune(self._samples.values(), self._clock())}
            self._samples = {k: v for k, v in self._samples.items() if k in keep}
            return True

    def samples(self) -> List[RunUsageSample]:
        with self._lock:
            return prune(self._samples.values(), self._clock())


def default_store(path: Optional[str] = None) -> IRunUsageStore:
    """The live wiring: ~/.mazda, beside mazda_mode.json and the mute file."""
    return JsonFileRunUsageStore(
        path or os.path.expanduser('~/.mazda/claude_sdk_usage.json'))
