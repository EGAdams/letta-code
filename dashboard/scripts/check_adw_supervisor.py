"""Focused supervisor check, also runnable inside the bridge's read-only jail.

These modules never invoke intake or Trainer code. Disable the unrelated global
conftest, which imports the entire server and foreign finance workspace.
"""
from pathlib import Path
import sys

import pytest

DASHBOARD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASHBOARD))
TESTS = (
    'test_adw_supervisor.py', 'test_supervisor_sources.py', 'test_model_registry.py',
    'test_worker_activity.py', 'test_worker_supervisor.py',
)

if __name__ == '__main__':
    raise SystemExit(pytest.main(['--noconftest', '-p', 'no:cacheprovider', '-q',
                                 *[str(DASHBOARD / 'tests' / name) for name in TESTS]]))
