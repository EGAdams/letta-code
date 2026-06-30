#!/usr/bin/env python3
"""
project_memfs_to_blocks.py — the memfs -> core-memory-block projector.

Why this exists
---------------
On this self-hosted Letta deployment (0.16.7) the documented design is "the
server projects system/** files into attached blocks." That projection is NOT a
native Letta feature in 0.16.7 (there is no /v1/.../project or /sync endpoint),
so the agent's memfs `state.git` and its live core-memory blocks drift apart:
files pushed to memfs (e.g. report_html_contract.md) never reach the running
agent, because the agent only reads core-memory blocks (Postgres).

This script IS that missing projector. It reads the agent's memfs files and
upserts a core-memory block per file, so memfs becomes the source of truth and
blocks are the projection — exactly as the design intends.

Safety properties
-----------------
- ADDITIVE ONLY. It never deletes or detaches a block. Blocks that have no
  corresponding memfs file (db_schema, environment, persona, ...) are left
  untouched. So it can never destroy live memory.
- Idempotent. A block whose value already equals the file body is skipped.
- PATCHes by block ID, never by label — block labels contain "/" which the
  /core-memory/blocks/{label} route mishandles.
- Frontmatter (--- ... ---) is stripped from the file body before projecting,
  matching how existing blocks store plain markdown.

Scope
-----
By default only TOP-LEVEL `system/*.md` files are projected (the agent's
operational procedures). Nested paths like `system/project/**` are repo-meta
(setup history, notes) and are skipped unless --include-nested is passed.

Usage
-----
  python3 scripts/project_memfs_to_blocks.py --agent <agent_id> [--dry-run]
      [--base-url http://100.80.49.10:8283]
      [--memdir /home/adamsl/.letta/agents/<agent_id>/memory]
      [--include-nested] [--no-recompile]

Exit code is non-zero if any block failed to project.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.environ.get("LETTA_BASE_URL", "http://100.80.49.10:8283")


def _req(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    api_key = os.environ.get("LETTA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        return resp.status, (json.loads(raw) if raw.strip() else None)


def strip_frontmatter(text):
    """Remove a leading YAML frontmatter block (--- ... ---), return the body."""
    if not text.startswith("---"):
        return text.lstrip("\n")
    lines = text.splitlines(keepends=True)
    # lines[0] is the opening '---'; find the closing one.
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return "".join(lines[i + 1:]).lstrip("\n")
    return text  # no closing fence — treat whole thing as body


def ensure_memdir(agent_id, base_url, memdir):
    """Clone the agent's state.git if missing, else pull --ff-only."""
    remote = f"{base_url}/v1/git/{agent_id}/state.git"
    if os.path.isdir(os.path.join(memdir, ".git")):
        subprocess.run(["git", "-C", memdir, "pull", "--ff-only", "origin", "main"],
                       check=False, capture_output=True)
    else:
        os.makedirs(os.path.dirname(memdir), exist_ok=True)
        subprocess.run(["git", "clone", remote, memdir], check=True, capture_output=True)
    return memdir


def collect_files(memdir, include_nested):
    sysdir = os.path.join(memdir, "system")
    out = {}
    for root, _dirs, files in os.walk(sysdir):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, memdir)  # e.g. system/foo.md
            label = rel[:-3]  # strip .md -> system/foo
            depth = label.count("/")  # system/foo == 1; system/project/x == 2+
            if depth > 1 and not include_nested:
                continue
            with open(full, encoding="utf-8") as f:
                out[label] = strip_frontmatter(f.read()).rstrip("\n") + "\n"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--memdir")
    ap.add_argument("--include-nested", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-recompile", action="store_true")
    args = ap.parse_args()

    agent_id = args.agent
    base = args.base_url.rstrip("/")
    memdir = args.memdir or f"/home/adamsl/.letta/agents/{agent_id}/memory"

    ensure_memdir(agent_id, base, memdir)
    files = collect_files(memdir, args.include_nested)
    if not files:
        print("No system/*.md files found — nothing to project.")
        return 0

    # Current live blocks for this agent: label -> (id, value)
    _, blocks = _req("GET", f"{base}/v1/agents/{agent_id}/core-memory/blocks")
    by_label = {b["label"]: b for b in blocks}

    created, updated, skipped, failed = [], [], [], []
    for label, body in sorted(files.items()):
        existing = by_label.get(label)
        try:
            if existing is None:
                if args.dry_run:
                    created.append(label + " (dry-run)")
                    continue
                _, blk = _req("POST", f"{base}/v1/blocks/",
                              {"label": label, "value": body})
                bid = blk["id"]
                _req("PATCH", f"{base}/v1/agents/{agent_id}/core-memory/blocks/attach/{bid}")
                created.append(label)
            elif existing.get("value", "") != body:
                if args.dry_run:
                    updated.append(label + " (dry-run)")
                    continue
                _req("PATCH", f"{base}/v1/blocks/{existing['id']}", {"value": body})
                updated.append(label)
            else:
                skipped.append(label)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            detail = ""
            if isinstance(e, urllib.error.HTTPError):
                try:
                    detail = " :: " + e.read().decode()[:300]
                except Exception:
                    pass
            failed.append(f"{label}: {e}{detail}")

    if not args.dry_run and (created or updated) and not args.no_recompile:
        try:
            _req("POST", f"{base}/v1/agents/{agent_id}/recompile")
        except Exception as e:
            print(f"WARN: recompile failed: {e}", file=sys.stderr)

    print(f"agent={agent_id}")
    print(f"  created: {created}")
    print(f"  updated: {updated}")
    print(f"  skipped (already in sync): {len(skipped)}")
    if failed:
        print(f"  FAILED: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
