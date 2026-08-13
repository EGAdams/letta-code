#!/usr/bin/env python3
"""Persistent APS runner adapter for the Python acceptance runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "acceptance"))

from acceptance_runtime import run_feature  # noqa: E402


def _run_job(request: dict) -> dict:
    feature_path = Path(request["feature_json"])
    feature = json.loads(feature_path.read_text())
    work_dir = Path(request["work_dir"]).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    captured = io.StringIO()
    started = time.monotonic_ns()
    original_dir = Path.cwd()
    try:
        os.chdir(work_dir)
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            exit_code = run_feature(feature)
    finally:
        os.chdir(original_dir)
    duration = time.monotonic_ns() - started
    return {
        "id": request.get("id", ""),
        "outcome": "test_success" if exit_code == 0 else "test_failure",
        "output": captured.getvalue(),
        "error": "",
        "duration": duration,
    }


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = ""
        try:
            request = json.loads(line)
            request_id = request.get("id", "")
            response = _run_job(request)
        except Exception as error:  # protocol errors are infrastructure errors
            response = {
                "id": request_id,
                "outcome": "infrastructure_error",
                "output": "",
                "error": f"{type(error).__name__}: {error}",
                "duration": 0,
            }
        print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
