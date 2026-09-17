"""The deterministic intake facade: cheapest-reliable-tool-first classify+parse.

When a scan finishes, the dashboard fires POST /api/process-document. The
cheapest reliable tool runs FIRST — the deterministic intake facade
(mazda_intake.py: classify + parse) — and its result is rendered inline within
seconds. The deeper, agentic stages (investigate -> categorize -> store) are
Mazda's job; they are dispatched fire-and-forget elsewhere. Governing rule:
cheapest reliable tool first; LLM only when confidence < 0.90 (the facade
enforces that threshold itself).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Callable

#: The pipeline stages the deterministic facade does NOT run — delegated to Mazda.
MAZDA_DELEGATED_STAGES = ('investigate', 'categorize', 'store')


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    mazda_intake_facade: str
    mazda_intake_python: str
    rol_finances_dir: str
    timeout_sec: float


def run_intake_facade(deps: Collaborators, image_path, org_id=1, engine='gemini'):
    """Run the deterministic intake facade (classify + parse) on one document.

    Returns the facade's structured JSON dict (always carrying an `ok` key).
    Never raises — a missing facade, bad exit, or unparseable stdout becomes
    {'ok': False, 'error': ...} so the caller can always render something inline.
    """
    if not os.path.isfile(image_path):
        return {'ok': False, 'error': f'Scanned image not found: {image_path}'}
    if not os.path.isfile(deps.mazda_intake_facade):
        return {'ok': False,
                'error': f'Intake facade not found: {deps.mazda_intake_facade}'}
    python = (deps.mazda_intake_python
              if os.path.isfile(deps.mazda_intake_python) else 'python3')
    try:
        proc = subprocess.run(
            [python, deps.mazda_intake_facade, image_path,
             f'--org-id={org_id}', '--enable-parse', f'--engine={engine}'],
            cwd=deps.rol_finances_dir,
            capture_output=True, text=True,
            timeout=deps.timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False,
                'error': f'Intake facade timed out after {deps.timeout_sec}s'}
    except Exception as exc:
        return {'ok': False, 'error': f'Failed to run intake facade: {exc}'}
    out = (proc.stdout or '').strip()
    # Sub-modules (e.g. LlmPdfParser) may print progress lines to stdout before
    # the final JSON object.  Find the first '{' so those stray lines don't
    # poison json.loads.
    json_start = out.find('{')
    if json_start > 0:
        out = out[json_start:]
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        err = (proc.stderr or '').strip() or out or f'exit {proc.returncode}'
        return {'ok': False, 'error': f'Intake facade returned no JSON: {err[:300]}'}


def build_pipeline_result(facade, mazda_dispatched):
    """Pure shaper: facade dict + dispatch flag → the inline pipeline result.

    Mirrors classify_scan_result — pure, no I/O, unit-tested. Produces an
    ordered `stages` list so the UI can render the full classify → parse →
    investigate → categorize → store pipeline, with the deterministic front half
    filled in and the agentic back half marked delegated (Mazda) or pending.
    """
    facade = facade or {}
    ok = bool(facade.get('ok'))
    classify = {
        'name': 'classify',
        'status': 'done' if ok else 'error',
        'doc_kind': facade.get('doc_kind'),
        'routing_key': facade.get('routing_key'),
        'vendor': facade.get('vendor'),
        'confidence': facade.get('confidence'),
        'method': facade.get('classification_method'),
        'recommended_action': facade.get('recommended_action'),
    }
    parsed = facade.get('parsed')
    parse = {
        'name': 'parse',
        'status': 'done' if (ok and parsed) else ('skipped' if ok else 'error'),
        'parsed': parsed,
    }
    delegated = [
        {'name': stage,
         'status': 'delegated' if mazda_dispatched else 'pending',
         'owner': 'mazda' if mazda_dispatched else None}
        for stage in MAZDA_DELEGATED_STAGES
    ]
    return {
        'ok': ok,
        'error': facade.get('error'),
        'mazda_dispatched': bool(mazda_dispatched),
        'stages': [classify, parse, *delegated],
    }
