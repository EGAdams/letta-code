#!/usr/bin/env python3
"""Add (or rotate) the ChatGPT notes-bridge client in the shared clients.json.

Run it on the dashboard host, as whichever user owns SCAN_BRIDGE_CONFIG_DIR
(default ~/.config/scan_bridge). Without --token-file it prints the plaintext
token exactly once -- then run it by hand, never from an agent, and never
commit or log that output; store it as NOTES_BRIDGE_TOKEN wherever
NotesBridgeClient (dashboard/notes_bridge_client.py) runs. The file on disk
keeps only the token's SHA-256, matching every other scan-bridge client -- see
scan_jobs/auth.py.

Usage:
    python3 scripts/provision_notes_bridge_client.py [--name NAME] [--rotate]
    python3 scripts/provision_notes_bridge_client.py --name agent-bridge-notes \\
        --token-file ~/.config/startrek_notes/notes_token [--rotate]

With --token-file the token is written to that file (mode 0600, parent 0700)
and is NOT printed, so an agent or a log never sees it. The Star Trek Bridge
worker reads its notes token from ~/.config/startrek_notes/notes_token.

Merges into the existing file: every other client's entry (including any
scanner:* worker) is left untouched. Refuses to run if a client with the same
name already exists unless --rotate is given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
from pathlib import Path

DEFAULT_NAME = "chatgpt-notes-bridge"
SCOPES = ("notes:read", "notes:write")


def config_dir() -> Path:
    return Path(os.environ.get("SCAN_BRIDGE_CONFIG_DIR") or Path.home() / ".config/scan_bridge")


def load_clients(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    clients = data.get("clients", [])
    if not isinstance(clients, list):
        raise SystemExit(f"{path} does not hold the expected {{'clients': [...]}} shape")
    return clients


def write_token_file(target: Path, token: str) -> None:
    """Atomically write the token, owner-only, without ever echoing it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, stat.S_IRWXU)
    tmp = target.with_name(f".{target.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--rotate", action="store_true",
                         help="Replace an existing client with this name instead of refusing.")
    parser.add_argument("--token-file", type=Path, default=None,
                        help="Write the token to this file (0600) instead of printing it.")
    args = parser.parse_args(argv)

    path = config_dir() / "clients.json"
    clients = load_clients(path)
    existing = next((c for c in clients if c.get("name") == args.name), None)
    if existing is not None and not args.rotate:
        print(f"A client named {args.name!r} already exists in {path}. "
              f"Pass --rotate to replace its token, or --name to add a different one.",
              file=sys.stderr)
        return 1

    token = secrets.token_urlsafe(32)
    entry = {
        "name": args.name,
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "scopes": list(SCOPES),
    }
    clients = [c for c in clients if c.get("name") != args.name] + [entry]

    if args.token_file is not None:
        # Written before clients.json, so a failure here leaves no hash without its token.
        write_token_file(args.token_file.expanduser(), token)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"clients": clients}, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 -- TokenAuthorizer refuses anything wider

    print(f"Provisioned {args.name!r} with scopes {list(SCOPES)} in {path}.")
    if args.token_file is not None:
        print(f"Token written to {args.token_file} (mode 0600); it was not printed.")
        return 0
    print("Token (shown once; this script does not store it anywhere):")
    print(token)
    print("\nExport it where NotesBridgeClient runs, e.g.:")
    print(f"  export NOTES_BRIDGE_TOKEN={token!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
