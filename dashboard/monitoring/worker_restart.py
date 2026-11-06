"""Narrow, authenticated restart command for the supervised bridge worker."""
from __future__ import annotations

import hmac
import os
import subprocess

SERVICE = "agent-bridge-worker.service"


def configured() -> bool:
    return bool(os.environ.get("WORKER_RESTART_TOKEN"))


def authorize(value: str | None) -> bool:
    expected = os.environ.get("WORKER_RESTART_TOKEN", "")
    supplied = (value or "").removeprefix("Bearer ")
    return bool(expected) and hmac.compare_digest(supplied, expected)


def restart(authorization: str | None) -> dict:
    if not configured():
        return {"ok": False, "configured": False, "text": "Worker restart is not configured."}
    if not authorize(authorization):
        return {"ok": False, "configured": True, "text": "Worker restart is not authorized."}
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", SERVICE],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "configured": True, "text": f"Worker restart failed: {exc}"}
    if result.returncode:
        detail = (result.stderr or result.stdout or "systemd returned a failure").strip()
        return {"ok": False, "configured": True, "text": f"Worker restart failed: {detail}"}
    return {"ok": True, "configured": True, "text": f"Restart requested for {SERVICE}."}
