"""Storing a whole corrected statement through Mazda's own store script.

The script is not wrapped or reimplemented -- duplicate detection, the
credit/payment split, vendor resolution to NEEDS_VENDOR_KEY and the
scanned-statement archive are all its behavior, unchanged. Running it from here
is what lets a human "be Mazda" while MAZDA_DECISION_MODE=human_only.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any

# The same subprocess runner the quarantined-statement retry path uses. Sharing
# it (rather than writing a second one) keeps one answer to "which JSON object
# in this stdout is the report?" -- a question already got wrong once, see
# statement_review._parse_report_output and manual_entry._extract_json_result.
from statement_review import _run_store

from finance.statement_commands import (
    build_annotation_command,
    build_store_command,
    build_store_payload,
)
from finance.statement_models import (
    CommandResult,
    StatementStoreRequest,
    StatementStoreResponse,
)
from finance.statement_ports import ICommandRunner, IStatementStore


class SubprocessCommandRunner(ICommandRunner):
    """Runs a command with PYTHONPATH=rol_finances, as Mazda's executor does."""

    def __init__(self, runner=None) -> None:
        self._runner = runner or _run_store

    def run(self, command: Sequence[str]) -> CommandResult:
        return CommandResult.from_runner(self._runner(list(command)))


class ScriptStatementStore(IStatementStore):
    """Stores a whole statement, then annotates every row it touched.

    A failed store leaves nothing here to clean up: the script quarantines its
    own unstorable rows (that is what statement_review's review queue reads), so
    this adapter only reports.
    """

    def __init__(self, runner: ICommandRunner | None = None,
                 annotation_runner: ICommandRunner | None = None) -> None:
        self._runner = runner or SubprocessCommandRunner()
        self._annotation_runner = annotation_runner or self._runner

    def store(self, request: StatementStoreRequest) -> StatementStoreResponse:
        payload_path = self._write_payload(build_store_payload(request))
        if not payload_path:
            return StatementStoreResponse(
                ok=False, error="could not stage the statement payload for storage")
        try:
            result = self._runner.run(build_store_command(request, payload_path))
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass
        report = result.report
        if result.returncode != 0 or not report.get("ok", False):
            return _store_response(report, ok=False, error=result.failure_text)

        response = _store_response(report, ok=True)
        annotation_error = self._annotate(request, response)
        if annotation_error:
            # Same posture as statement_review.resolve_review: the rows ARE
            # stored, so this reports a failed annotation step with the store's
            # counts intact -- never as "nothing was saved".
            return _store_response(report, ok=False, error=annotation_error)
        return response

    def _annotate(self, request: StatementStoreRequest,
                  response: StatementStoreResponse) -> str | None:
        expense_ids = response.annotatable_expense_ids
        if not expense_ids:
            return None
        result = self._annotation_runner.run(
            build_annotation_command(request.image_path, expense_ids))
        report = result.report
        if result.returncode == 0 and report.get("ok", False):
            return None
        problems = report.get("problems") or []
        return ("; ".join(str(problem) for problem in problems)
                or result.failure_text or "handwritten category step failed")

    @staticmethod
    def _write_payload(payload: Mapping[str, Any]) -> str:
        try:
            handle = tempfile.NamedTemporaryFile(
                "w", suffix=".json", prefix="statement_breakup_",
                delete=False, encoding="utf-8")
        except OSError:
            return ""
        try:
            with handle:
                json.dump(payload, handle)
        except (OSError, TypeError, ValueError):
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            return ""
        return handle.name


def _int_list(values: Any) -> list[int]:
    result = []
    for value in values if isinstance(values, list) else []:
        if isinstance(value, bool):
            continue
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _count(report: Mapping[str, Any], key: str) -> int:
    value = report.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _store_response(report: Mapping[str, Any], *, ok: bool,
                    error: str | None = None) -> StatementStoreResponse:
    """The script's report, typed -- counts preserved even on failure.

    A partial run ("3 stored, 1 failed") must not come back as zeros: the
    operator needs to know what already landed before deciding what to retry.
    """
    return StatementStoreResponse(
        ok=ok,
        transactions_parsed=_count(report, "transactions_parsed"),
        stored=_count(report, "stored"),
        duplicates=_count(report, "duplicates"),
        skipped_credits=_count(report, "skipped_credits"),
        uncategorized=_count(report, "uncategorized"),
        failed=_count(report, "failed"),
        expense_ids=_int_list(report.get("expense_ids")),
        duplicate_expense_ids=_int_list(report.get("duplicate_expense_ids")),
        problems=[str(problem) for problem in (report.get("problems") or [])],
        error=error,
    )
