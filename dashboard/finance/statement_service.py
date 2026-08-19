"""The statement-breakup use cases, composed entirely from injected ports."""

from __future__ import annotations

from finance.statement_models import (
    StatementBreakupRequest,
    StatementBreakupResponse,
    StatementStoreRequest,
    StatementStoreResponse,
)
from finance.statement_ports import (
    IStatementBreakupService,
    IStatementExtractor,
    IStatementIntakeRecorder,
    IStatementStore,
    NullStatementIntakeRecorder,
)


class StatementBreakupService(IStatementBreakupService):
    """Split a scanned statement, then store what the operator corrected.

    The two steps are separate use cases on purpose: everything between them is
    the human's -- reading the page, fixing a misread amount, walking Prev/Next.
    """

    def __init__(self, extractor: IStatementExtractor, store: IStatementStore,
                 recorder: IStatementIntakeRecorder | None = None) -> None:
        self._extractor = extractor
        self._store = store
        self._recorder = recorder or NullStatementIntakeRecorder()

    def break_up(self, request: StatementBreakupRequest) -> StatementBreakupResponse:
        return self._extractor.extract(request)

    def store(self, request: StatementStoreRequest) -> StatementStoreResponse:
        response = self._store.store(request)
        # Only a real store may claim the intake is complete: recording a failed
        # attempt would flip the page to "complete" with nothing in the table.
        if response.ok:
            self._recorder.record(request, response)
        return response
