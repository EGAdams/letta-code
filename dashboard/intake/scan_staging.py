"""Staging a scanned image where Mazda's tools can read it, and opening the
isolated Letta conversation the dispatch will run in.

Mazda has TWO executors: ``executor_run`` (this box's Letta MCP executor,
where rol_finances/MySQL live -- the PRIMARY intake path) and
``run_claude_code_sdk`` (the frita-executor container on the Win10 box, whose
mounted rol_finances venv is a broken symlink -- see the 2026-07-10 incident).
The scan is therefore staged LOCALLY first (authoritative) and mirrored to the
Win10 box best-effort.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    scan_output_ready: Callable
    scan_staging_host: str
    scan_staging_remote_dir: str
    letta_base_url: str
    mazda_agent_id: str


def stage_scan_for_mazda(deps: Collaborators, local_image_path):
    """Copy a scanned image to where Mazda's executor tools can actually read it.

    Copies into this box's rol_finances incoming_scans (executor_run's view —
    required) and mirrors to the Win10 box (run_claude_code_sdk's view —
    best-effort). Returns the staged path (identical on both boxes) or None
    when even the local copy failed — the caller must not hand Mazda a path
    she can't reach.
    """
    if not deps.scan_output_ready(local_image_path):
        print('[scan→mazda] Refusing to stage a missing or empty scan output')
        return None
    # Scanner output names are reusable (window_scan.jpg / scan_freezer.jpg), while a
    # Mazda conversation can remain active for minutes.  Never give two runs
    # the same mutable path: a late tool call from the older run could otherwise
    # read and store the newer scan.  Keep the scanner prefix for diagnostics,
    # and add both a dispatch-unique timestamp and a content fingerprint.
    source_name = os.path.basename(local_image_path)
    stem, suffix = os.path.splitext(source_name)
    try:
        with open(local_image_path, 'rb') as src:
            content_hash = hashlib.sha256(src.read()).hexdigest()[:12]
    except OSError as exc:
        print(f'[scan→mazda] Failed to fingerprint scan: {exc}')
        return None
    staged_name = f'{stem}_{time.time_ns()}_{content_hash}{suffix}'
    staged_path = f'{deps.scan_staging_remote_dir}/{staged_name}'
    try:
        os.makedirs(deps.scan_staging_remote_dir, exist_ok=True)
        shutil.copyfile(local_image_path, staged_path)
    except Exception as exc:
        print(f'[scan→mazda] Failed to stage scan locally for executor: {exc}')
        return None
    try:
        subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             deps.scan_staging_host, 'mkdir', '-p', deps.scan_staging_remote_dir],
            capture_output=True, text=True, timeout=15, check=True,
        )
        subprocess.run(
            ['scp', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
             local_image_path, f'{deps.scan_staging_host}:{staged_path}'],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except Exception as exc:
        print(f'[scan→mazda] Win10 mirror of scan failed (non-fatal — '
              f'executor_run reads the local copy): {exc}')
    return staged_path


def create_mazda_conversation(deps: Collaborators):
    """Create one isolated Letta conversation for one intake dispatch.

    Never fall back to Mazda's agent-default conversation: that would allow
    simultaneous Window and Freezer scans to share compacted context again.
    """
    try:
        agent_id = quote(deps.mazda_agent_id, safe='')
        req = urllib.request.Request(
            f'{deps.letta_base_url}/v1/conversations/?agent_id={agent_id}',
            data=b'{}',
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            conversation = json.loads(resp.read().decode())
        conversation_id = conversation.get('id')
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError('Letta returned no conversation id')
        return conversation_id
    except Exception as exc:
        print(f'[scan→mazda] Failed to create isolated conversation: {exc}')
        return None
