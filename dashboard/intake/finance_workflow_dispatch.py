"""Handing a scanned document to the finance application's own workflow.

Until now "Automatic" meant one thing: write the Mazda agent an eight-step
message and wait for her to run the store commands herself. The finance
application (``~/rol_finances/finance_app``) can now run those steps as code
and ask a model only what code cannot settle. This module is the dashboard's
side of that hand-off -- and nothing else:

* which engine the next document uses (``IntakeEngineService``),
* how the workflow is started (``IFinanceWorkflowRunner``; the live one runs
  the ``adw_interface_finance_intake`` ADW so the run shows in the debugger),
* what the scanner tab is told when a run ends without touching the books.

The dashboard never imports the finance code and never calls a model here.
A run that stores something announces itself through the same
``/api/expense-stored`` callback as before, so Recent Report is unchanged.

Engine, deliberately separate from the Automatic / Semi-Automatic switch:
that switch answers "may anything run without a person?"; this answers "what
runs". Semi-Automatic still wins -- it is checked first, in
``mazda_dispatch.dispatch_or_block``.

The default is the earlier engine. Nothing changes on a box until someone
sets ``FINANCE_INTAKE_ENGINE=finance_workflow`` or writes the engine file.

Falling back to the earlier path is allowed in exactly one case: the workflow
said, before writing anything, that this kind of document is not its to
handle (``unsupported``). A run that crashed is never retried on the other
path -- a second writer after an uncertain write is how duplicates are made.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Literal, Optional

from pydantic import Field, ValidationError

from contracts import StrictModel
from intake.intake_engine import FINANCE_WORKFLOW

#: Document kinds the facade can already name that stay on the earlier path.
STATEMENT_DOC_KINDS = frozenset({'statement', 'bank_statement'})

STATUS_SOURCE = 'finance_workflow'

#: workflow outcome -> the terminal status the scanner tab shows. Outcomes
#: that stored or attached something are absent on purpose: their callback
#: already set the record.
OUTCOME_STATUS: dict[str, str] = {
    'awaiting_vendor_review': 'awaiting_vendor_review',
    'needs_human_review': 'needs_human_review',
    'not_financial': 'complete',
    'halted': 'fail',
    'failed': 'fail',
}

NO_RESULT_DETAIL = (
    'The finance workflow ended without a result. Nothing was retried on the '
    'other path, because a write may have started. Check the run in the '
    'Terminal debugger before scanning this page again.')


class FinanceWorkflowRequest(StrictModel):
    """One document for the workflow, with the identity its record is keyed on."""

    document_path: str = Field(min_length=1)
    label: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    dispatched_at: float = Field(gt=0)


class FinanceWorkflowResult(StrictModel):
    """The few facts the dashboard needs from a finished run. Deliberately not
    the finance application's full result: amounts and ids reach the page
    through the stored-expense callback and the database, not through here."""

    run_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    problems: tuple[str, ...] = ()
    review_id: Optional[str] = None

    @classmethod
    def from_json(cls, text: str) -> Optional['FinanceWorkflowResult']:
        try:
            data = json.loads(text)
            return cls(run_id=str(data['run_id']), outcome=str(data['outcome']),
                       problems=tuple(str(p) for p in (data.get('problems') or ())),
                       review_id=data.get('review_id') or None)
        except (ValueError, KeyError, TypeError, ValidationError):
            return None


class IFinanceWorkflowRunner(ABC):
    """Runs one document through the finance workflow and waits for it."""

    @abstractmethod
    def run(self, request: FinanceWorkflowRequest) -> Optional[FinanceWorkflowResult]:
        """The run's result, or None when it ended without producing one."""


class AdwFinanceWorkflowRunner(IFinanceWorkflowRunner):
    """Starts the finance intake ADW as its own process, the way Scala's
    watcher starts hers: one process per document, visible in the debugger."""

    def __init__(self, python: str, adw_script: str, cwd: str,
                 timeout_seconds: float = 900.0):
        self._python, self._script, self._cwd = python, adw_script, cwd
        self._timeout = timeout_seconds

    def run(self, request: FinanceWorkflowRequest) -> Optional[FinanceWorkflowResult]:
        handle, result_path = tempfile.mkstemp(prefix='finance_intake_', suffix='.json')
        os.close(handle)
        try:
            subprocess.run(
                [self._python, self._script, 'scan intake',
                 '--scan', request.document_path, '--source', request.label,
                 '--conversation-id', request.conversation_id,
                 '--dispatched-at', repr(request.dispatched_at),
                 '--result-out', result_path],
                cwd=self._cwd, capture_output=True, text=True, timeout=self._timeout)
            with open(result_path, encoding='utf-8') as fh:
                return FinanceWorkflowResult.from_json(fh.read())
        except (OSError, subprocess.SubprocessError) as exc:
            print(f'[scan→finance] workflow run did not finish: {exc}')
            return None
        finally:
            try:
                os.unlink(result_path)
            except OSError:
                pass


def workflow_takes(facade: Any) -> bool:
    """Whether this document may start on the workflow at all.

    A statement the facade or the operator already named stays on the earlier
    path until its report can be built by code. Everything else starts here;
    the workflow classifies it and hands back what is not its own.
    """
    facade = facade or {}
    if facade.get('statement_preflight'):
        return False
    return str(facade.get('doc_kind') or 'unknown').strip().lower() not in STATEMENT_DOC_KINDS


def status_update(request: FinanceWorkflowRequest, status: str, detail: str) -> dict:
    """The mapping ``merge_recent_intake_status`` reads."""
    return {
        'conversation_id': request.conversation_id,
        'document_path': request.document_path,
        'dispatched_at': request.dispatched_at,
        'status': status,
        'status_source': STATUS_SOURCE,
        'detail': detail,
        'status_detail': detail,
    }


class FinanceWorkflowDispatcher:
    """Decides whether the workflow takes a document, and sees the run through."""

    def __init__(self, engine: Callable[[], str], runner: IFinanceWorkflowRunner,
                 merge_status: Callable[[dict], Any],
                 start: Callable[[Callable[[], None]], None] | None = None):
        self._engine, self._runner, self._merge_status = engine, runner, merge_status
        self._start = start or (lambda work: threading.Thread(target=work, daemon=True).start())

    def dispatch(self, document_path, label, facade, conversation_id, dispatched_at,
                 earlier_path: Callable[[], None]) -> bool:
        """True when the workflow took the document. False means "not mine":
        the caller carries on exactly as it did before this module existed."""
        if self._engine() != FINANCE_WORKFLOW or not workflow_takes(facade):
            return False
        try:
            request = FinanceWorkflowRequest(
                document_path=document_path, label=label,
                conversation_id=conversation_id, dispatched_at=float(dispatched_at))
        except (ValidationError, TypeError, ValueError):
            return False
        self._start(lambda: self.see_through(request, earlier_path))
        return True

    def see_through(self, request: FinanceWorkflowRequest,
                    earlier_path: Callable[[], None]) -> None:
        result = self._runner.run(request)
        if result is None:
            self._merge_status(status_update(request, 'fail', NO_RESULT_DETAIL))
            return
        if result.outcome == 'unsupported':
            print(f'[scan→finance] {request.label}: not handled by the workflow '
                  f'({"; ".join(result.problems)}); using the earlier path')
            earlier_path()
            return
        status = OUTCOME_STATUS.get(result.outcome)
        if status is None:
            return          # stored / evidence attached: the callback set the record
        detail = '; '.join(result.problems) or result.outcome.replace('_', ' ')
        if result.review_id:
            detail = f'{detail} (review {result.review_id[:8]})'
        self._merge_status(status_update(request, status, detail))
