"""Shared, durable generation for the dashboard Terminal view.

This is display state only.  It deliberately does not touch the worker ledger.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()
DEFAULT_STATE = Path(os.path.expanduser("~/.cache/agent_bridge/terminal_clear.json"))


def _path() -> Path:
    return Path(os.environ.get("TERMINAL_CLEAR_STATE", str(DEFAULT_STATE))).expanduser()


def epoch() -> int:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        result = value.get("epoch", 0) if isinstance(value, dict) else 0
        return result if isinstance(result, int) and result >= 0 else 0
    except (OSError, ValueError):
        return 0


def clear() -> dict:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        next_epoch = epoch() + 1
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({"epoch": next_epoch}), encoding="utf-8")
        os.replace(temporary, path)
    return {"ok": True, "terminal_clear_epoch": next_epoch}
