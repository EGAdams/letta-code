"""Subprocess adapter satisfying the bounded receipt-reader port."""
from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from finance.manual_entry import resolve_vendor_match
from finance.receipt_read_contracts import (
    IFocusedReceiptReader,
    ReceiptReadIntent,
)
from statement_review import RF_PYPATH, RF_VENV_PY


PREFILL_SCRIPT = Path(__file__).with_name('receipt_prefill_cli.py')
FOCUSED_READ_TIMEOUT_SECONDS = 65


class FocusedReceiptReader(IFocusedReceiptReader):
    def __init__(self, category_namer_factory, runner=None):
        self._category_namer_factory = category_namer_factory
        self._runner = runner or subprocess.run

    def read(self, image_path: str, model: str,
             intent: ReceiptReadIntent) -> tuple[bool, Mapping[str, object]]:
        command = [
            RF_VENV_PY,
            str(PREFILL_SCRIPT),
            '--image', image_path,
            '--model', model,
            '--intent', intent.value,
        ]
        env = dict(
            os.environ,
            PYTHONPATH=os.pathsep.join((
                # ``finance`` is the package beside this script, so Python
                # needs dashboard/ on sys.path, not the repository root.
                str(PREFILL_SCRIPT.parents[1]), RF_PYPATH,
            )),
        )
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=FOCUSED_READ_TIMEOUT_SECONDS,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, {'error': f'{type(exc).__name__}: {exc}'}

        payload = self._last_json_object(completed.stdout)
        if completed.returncode != 0 or not payload.get('ok'):
            return False, {
                'error': payload.get('error') or completed.stderr
                or 'focused receipt read failed',
            }
        payload.update(resolve_vendor_match(
            payload.get('merchant_name'),
            category_namer=self._category_namer_factory(),
        ))
        return True, payload

    @staticmethod
    def _last_json_object(stdout: str) -> dict:
        for line in reversed((stdout or '').splitlines()):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return {}
