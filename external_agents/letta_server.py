"""Resolve Letta server base URL consistently across agent scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_BASE_URL = "http://100.80.49.10:8283"
SETTINGS_PATH = Path("~/.letta/settings.json").expanduser()


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {}


def resolve_base_url() -> str:
    env_url = os.getenv("LETTA_BASE_URL")
    if env_url:
        return env_url

    settings = _load_settings()
    sessions = settings.get("sessionsByServer") or {}
    if sessions:
        server = next(iter(sessions.keys()), None)
        if server:
            if server.startswith("http://") or server.startswith("https://"):
                return server
            return f"http://{server}"
    return DEFAULT_BASE_URL