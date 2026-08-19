"""Dashboard-side adapters, built from injected callables only.

The two collaborators the statement path needs from the dashboard -- its
existing statement preflight and its intake record -- live in server.py as plain
functions. These adapters wrap them behind the ports so nothing in finance/
imports server.py, and so server.py keeps only the wiring: the composition root
passes the functions in, and every rule about how they are used lives here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from finance.statement_models import StatementStoreRequest, StatementStoreResponse
from finance.statement_ports import (
    IStatementIntakeRecorder,
    IStatementPreflightGateway,
)


class CallableStatementPreflight(IStatementPreflightGateway):
    """The automatic pipeline's own statement preflight, as an injectable port.

    ``facade_for`` supplies the synthetic classification the "Not a receipt —
    process as statement" button already uses: the operator has looked at the
    page via Show Image, so the paid vision classify call is skipped. The
    extraction itself is unavoidable -- several transactions have to be read off
    the page somehow -- and is what ``run_preflight`` performs.
    """

    def __init__(self, run_preflight: Callable[..., Mapping[str, Any] | None],
                 build_payload: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
                 facade_for: Callable[[str], Mapping[str, Any]],
                 doc_kind: str = "statement") -> None:
        self._run_preflight = run_preflight
        self._build_payload = build_payload
        self._facade_for = facade_for
        self._doc_kind = doc_kind

    def run(self, image_path: str, metadata: Mapping[str, Any],
            engine: str) -> Mapping[str, Any] | None:
        return self._run_preflight(
            image_path, self._facade_for(self._doc_kind), metadata=metadata,
            engine=engine)

    def rows(self, image_path: str,
             preflight: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """The per-statement rows the store will actually see.

        Read through the payload builder rather than off the preflight's own
        top-level ``transactions`` summary: that summary drops rows the parser
        could not fully read, and those are exactly the ones the operator is
        here to repair.
        """
        payload = self._build_payload(image_path, preflight)
        statements = payload.get("statements") or [{}]
        return [row for row in (statements[0].get("transactions") or [])
                if isinstance(row, dict)]


class CallbackStatementIntakeRecorder(IStatementIntakeRecorder):
    """Folds a hand-completed statement store into the intake record.

    Emits the same STEP-8-shaped event Mazda posts to /api/expense-stored and
    submit_manual_receipt_entry merges for a receipt, so the Verified
    Transactions table and the intake status flip exactly as they do when an
    agent did the work: the page must not be able to tell who stored it.
    """

    def __init__(self, merge_event: Callable[[Mapping[str, Any]], Any],
                 invalidate_receipt_index: Callable[[], Any] | None = None) -> None:
        self._merge_event = merge_event
        self._invalidate_receipt_index = invalidate_receipt_index

    def record(self, request: StatementStoreRequest,
               response: StatementStoreResponse) -> None:
        if self._invalidate_receipt_index is not None:
            # The store moved files and inserted rows out-of-process, invisible
            # to the server's cached receipt index until its TTL expires --
            # without this the View Receipt/evidence links right after a save
            # read a stale index and report no document at all.
            self._invalidate_receipt_index()
        self._merge_event({
            'conversation_id': request.conversation_id,
            'document_path': request.image_path,
            'expense_ids': list(response.expense_ids),
            'duplicate_expense_ids': list(response.duplicate_expense_ids),
            'parsed': response.transactions_parsed or len(request.transactions),
            'stored': response.stored,
            'doc_kind': 'statement',
            'vendor': request.bank_name,
            'status': 'complete',
            'status_detail': (
                f'Broken up by hand (human_only mode) — '
                f'{response.transactions_parsed} read, {response.stored} stored, '
                f'{response.duplicates} already on file, '
                f'{response.skipped_credits} credit/payment skipped.'),
        })
