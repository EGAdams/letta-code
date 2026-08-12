"""Windows-side control service for the Rosemary46 recovery agent.

The service deliberately exposes operations, not a shell.  Every operation maps
to a fixed executable and fixed argument shape; callers cannot provide command
strings or arbitrary paths.  It is intended to run on Rosemary46 Windows.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DISTRO = os.environ.get("SHELIA_WSL_DISTRO", "Ubuntu-24.04")
LINUX_NODE = os.environ.get("SHELIA_LINUX_NODE", "100.72.34.38")
KEEPALIVE_TASK = os.environ.get(
    "SHELIA_KEEPALIVE_TASK", "Rosemary46 WSL Tailscale Keepalive"
)
LISTEN_HOST = os.environ.get("SHELIA_LISTEN_HOST", "100.106.176.58")
LISTEN_PORT = int(os.environ.get("SHELIA_LISTEN_PORT", "8795"))
TOKEN_FILE = os.environ.get(
    "SHELIA_TOKEN_FILE", r"C:\ProgramData\SheliaRecovery\shelia-token.txt"
)
AUTH_TOKEN = os.environ.get("SHELIA_AUTH_TOKEN", "")
if not AUTH_TOKEN:
    try:
        AUTH_TOKEN = Path(TOKEN_FILE).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        AUTH_TOKEN = ""


def _exe(windows_name: str, linux_name: str | None = None) -> str:
    """Resolve one fixed executable on either Windows or WSL."""
    if os.name == "nt":
        return windows_name
    if windows_name == "tailscale.exe":
        return "/mnt/c/Program Files/Tailscale/tailscale.exe"
    if windows_name in {"schtasks.exe", "wsl.exe", "ssh.exe"}:
        return f"/mnt/c/Windows/System32/{windows_name}"
    return linux_name or windows_name


def _local_wsl(args: list[str], timeout: float = 15.0) -> dict[str, Any]:
    """Run a fixed local Linux operation when the service itself runs in WSL."""
    return _run(args, timeout)


class RecoveryError(RuntimeError):
    """An expected, actionable recovery operation failure."""


def _run(args: list[str], timeout: float = 15.0) -> dict[str, Any]:
    """Run one fixed executable and return redacted structured output."""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RecoveryError(
            f"could not execute required command {args[0]}: {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RecoveryError(f"operation timed out: {args[0]}") from exc
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-4000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def _json_command(args: list[str], timeout: float = 15.0) -> Any:
    result = _run(args, timeout)
    if not result["ok"]:
        raise RecoveryError(result["stderr"] or result["stdout"] or "command failed")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        raise RecoveryError("Windows command returned invalid JSON") from exc


def _task_state() -> dict[str, Any]:
    result = _run(
        [_exe("schtasks.exe"), "/query", "/tn", KEEPALIVE_TASK, "/fo", "csv", "/nh"]
    )
    return {"ok": result["ok"], "output": result["stdout"], "error": result["stderr"]}


def _tailscale_summary() -> dict[str, Any]:
    """Return only the two Rosemary peer records, not the whole tailnet roster."""
    try:
        command = [_exe("tailscale.exe"), "status", "--json"]
        data = _json_command(command)
    except RecoveryError as exc:
        return {"ok": False, "error": str(exc)}
    peers = []
    peer_map = data.get("Peer") if isinstance(data, dict) else {}
    for peer in (peer_map or {}).values():
        identity = f"{peer.get('HostName', '')} {peer.get('DNSName', '')}".lower()
        if "rosemary46" not in identity:
            continue
        peers.append(
            {
                "host": peer.get("HostName"),
                "addresses": peer.get("TailscaleIPs", [])[:2],
                "online": peer.get("Online"),
                "key_expiry": peer.get("KeyExpiry"),
                "last_seen": peer.get("LastSeen"),
                "os": peer.get("OS"),
            }
        )
    return {"ok": True, "peers": peers}


def status() -> dict[str, Any]:
    """Return host, task, WSL, and Tailscale evidence without changing state."""
    task = _task_state()
    wsl = (
        _run([_exe("wsl.exe", "wsl"), "-l", "-v"])
        if os.name == "nt"
        else _local_wsl(["systemctl", "is-active", "tailscaled"])
    )
    tailscale = _tailscale_summary()
    return {
        "ok": task["ok"] and wsl["ok"] and tailscale["ok"],
        "host": {"computer": os.environ.get("COMPUTERNAME", "unknown")},
        "task": task,
        "wsl": {"ok": wsl["ok"], "output": wsl["stdout"], "error": wsl["stderr"]},
        "tailscale": tailscale,
        "distro": DISTRO,
        "linux_node": LINUX_NODE,
        "timestamp": int(time.time()),
    }


def start_keepalive() -> dict[str, Any]:
    """Start the pre-installed keepalive task; safe to repeat."""
    result = _run([_exe("schtasks.exe"), "/run", "/tn", KEEPALIVE_TASK])
    return {
        "ok": result["ok"],
        "task": KEEPALIVE_TASK,
        "output": result["stdout"],
        "error": result["stderr"],
    }


def restart_wsl_tailscale() -> dict[str, Any]:
    """Restart tailscaled inside the fixed, documented WSL distro."""
    args = ["wsl.exe", "-d", DISTRO, "--", "sudo", "systemctl", "restart", "tailscaled"]
    if os.name != "nt":
        args = ["sudo", "-n", "systemctl", "restart", "tailscaled"]
    result = _run([_exe(args[0], args[0]), *args[1:]])
    return {
        "ok": result["ok"],
        "distro": DISTRO,
        "output": result["stdout"],
        "error": result["stderr"],
    }


def reauth_instructions() -> dict[str, Any]:
    """Explain interactive reauthentication without attempting an unattended login."""
    return {
        "ok": True,
        "requires_local_interaction": True,
        "windows": ["tailscale.exe up --force-reauth"],
        "wsl": [f"wsl.exe -d {DISTRO} -- sudo tailscale up --force-reauth"],
        "warning": "Complete the authorization URL locally; Shelia never handles auth tokens.",
    }


def verify_recovery() -> dict[str, Any]:
    """Verify the Linux node's Tailscale daemon and SSH using fixed arguments."""
    tailscale = _run([_exe("tailscale.exe"), "status", "--json"])
    wsl = (
        _run(["systemctl", "is-active", "tailscaled"])
        if os.name != "nt"
        else _run(
            ["wsl.exe", "-d", DISTRO, "--", "systemctl", "is-active", "tailscaled"]
        )
    )
    ssh_exe = "ssh" if os.name != "nt" else "ssh.exe"
    ssh = _run(
        [
            ssh_exe,
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            f"adamsl@{LINUX_NODE}",
            "echo LINUX_AUTH_OK",
        ],
        timeout=12,
    )
    return {
        "ok": tailscale["ok"]
        and wsl["ok"]
        and ssh["ok"]
        and "LINUX_AUTH_OK" in ssh["stdout"],
        "tailscale": {"ok": tailscale["ok"], "error": tailscale["stderr"]},
        "wsl_tailscaled": {
            "ok": wsl["ok"],
            "output": wsl["stdout"],
            "error": wsl["stderr"],
        },
        "ssh": {"ok": ssh["ok"], "output": ssh["stdout"], "error": ssh["stderr"]},
    }


OPERATIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "status": status,
    "start_keepalive": start_keepalive,
    "restart_wsl_tailscale": restart_wsl_tailscale,
    "reauth_instructions": reauth_instructions,
    "verify_recovery": verify_recovery,
}


class RecoveryHandler(BaseHTTPRequestHandler):
    server_version = "SheliaRecovery/1.0"

    def _reply(self, code: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {AUTH_TOKEN}" if AUTH_TOKEN else ""
        return bool(AUTH_TOKEN) and secrets.compare_digest(supplied, expected)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._reply(200, {"ok": bool(AUTH_TOKEN), "service": "shelia-recovery"})
            return
        if not self._authorized():
            self._reply(401, {"ok": False, "error": "missing or invalid bearer token"})
            return
        if self.path == "/v1/status":
            self._dispatch(status)
        else:
            self._reply(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._reply(401, {"ok": False, "error": "missing or invalid bearer token"})
            return
        path = self.path.removeprefix("/v1/actions/")
        operation = OPERATIONS.get(path)
        if operation is None:
            self._reply(404, {"ok": False, "error": "unknown recovery operation"})
            return
        self._dispatch(operation)

    def _dispatch(self, operation: Callable[[], dict[str, Any]]) -> None:
        try:
            result = operation()
            self._reply(200 if result.get("ok", False) else 503, result)
        except RecoveryError as exc:
            self._reply(503, {"ok": False, "error": str(exc)})

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def serve() -> None:
    if not AUTH_TOKEN:
        raise SystemExit(
            "SHELIA_AUTH_TOKEN must be configured; refusing unauthenticated startup"
        )
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), RecoveryHandler)
    server.serve_forever()


if __name__ == "__main__":
    serve()
