"""Adapter: each request runs the finance ADW with observable code phases."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .contracts import WorkRequest, WorkResult
from finance.expense_edit_audit import IExpenseEditCommand
from .interfaces import JsonAdwRunner


class FinanceAdwRunner:
    def __init__(self, root: Path, dashboard_url: str):
        self.root, self.dashboard_url = root, dashboard_url

    def run(self, request: WorkRequest) -> WorkResult:
        result = self.invoke('adw_receptionist_tax.py', request.model_dump(),
                             ['--dashboard-url', self.dashboard_url])
        return WorkResult.model_validate(result)

    def invoke(self, script: str, payload: dict, arguments: list[str] | None = None) -> dict:
        uv = shutil.which('uv') or str(Path.home() / '.local/bin/uv')
        with tempfile.TemporaryDirectory(prefix='toyota-adw-') as directory:
            source, result = Path(directory) / 'request.json', Path(directory) / 'result.json'
            source.write_text(json.dumps(payload))
            command = [uv, 'run', 'adws/' + script, '--request-file', str(source),
                       '--result-file', str(result), *(arguments or [])]
            completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=90,
                                       env={**os.environ, 'PYTHONUNBUFFERED': '1'})
            if not result.is_file():
                detail = (completed.stderr or completed.stdout)[-1500:]
                raise RuntimeError(f'The receptionist ADW did not publish a result: {detail}')
            return json.loads(result.read_text())


class FinanceExpenseEditCommand(IExpenseEditCommand):
    """Command Adapter: the HTTP save remains an ADW with its own code phases."""
    def __init__(self, runner: JsonAdwRunner):
        self.runner = runner

    def execute(self, request: dict) -> dict:
        return self.runner.invoke('adw_receptionist_edit.py', request)
