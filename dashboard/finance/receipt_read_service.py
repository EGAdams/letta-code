"""Strategy-based application service for manual receipt reading."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from finance.receipt_read_contracts import (
    IFocusedReceiptReader,
    IReceiptReadStrategy,
    ReceiptReadIntent,
    ReceiptReadRequest,
    ReceiptReadResponse,
    SHAPE_MANY_EXPENSES,
    SHAPE_ONE_EXPENSE,
)
from finance.receipt_read_outcome import ReceiptReadOutcome
from finance.statement_models import (
    StatementBreakupRequest,
    StatementBreakupResponse,
)


class IDocumentClassifier(ABC):
    @abstractmethod
    def classify(self, image_path: str) -> str:
        ...


class IForensicReceiptReader(ABC):
    @abstractmethod
    def read(self, image_path: str,
             model: str) -> tuple[bool, Mapping[str, Any]]:
        ...


class CallableDocumentClassifier(IDocumentClassifier):
    def __init__(self, classify_fn):
        self._classify_fn = classify_fn

    def classify(self, image_path: str) -> str:
        return str(self._classify_fn(image_path) or '')


class CallableForensicReceiptReader(IForensicReceiptReader):
    def __init__(self, read_fn):
        self._read_fn = read_fn

    def read(self, image_path: str,
             model: str) -> tuple[bool, Mapping[str, Any]]:
        return self._read_fn(image_path, model)


class FocusedReceiptReadStrategy(IReceiptReadStrategy):
    """Circled-only or total-only, delegated to a bounded vision reader."""

    def __init__(self, intent: ReceiptReadIntent,
                 reader: IFocusedReceiptReader):
        if intent is ReceiptReadIntent.SEVERAL_EXPENSES:
            raise ValueError('Several Expenses requires the forensic strategy')
        self._intent = intent
        self._reader = reader

    def read(self, request: ReceiptReadRequest) -> ReceiptReadResponse:
        ok, payload = self._reader.read(
            request.image_path, request.model, self._intent)
        prefill = dict(payload or {})
        return ReceiptReadResponse(
            ok=bool(ok),
            shape=SHAPE_ONE_EXPENSE,
            intent=self._intent,
            model=request.model,
            doc_kind='receipt',
            receipt={'ok': bool(ok), **prefill},
            error=None if ok else str(prefill.get('error') or 'read failed'),
        )


def _carries_transactions(response: ReceiptReadResponse) -> bool:
    payload = response.statement or {}
    rows = payload.get('transactions')
    return bool(isinstance(rows, (list, tuple)) and rows)


class ForensicReceiptReadStrategy(IReceiptReadStrategy):
    """Full document classification and item/transaction extraction."""

    def __init__(self, classifier: IDocumentClassifier,
                 receipts: IForensicReceiptReader, statements,
                 statement_doc_kinds=('statement', 'bank_statement')):
        self._classifier = classifier
        self._receipts = receipts
        self._statements = statements
        self._statement_doc_kinds = tuple(statement_doc_kinds)

    def read(self, request: ReceiptReadRequest) -> ReceiptReadResponse:
        doc_kind = self._classify(request.image_path)
        if doc_kind in self._statement_doc_kinds:
            return self._read_statement(request, doc_kind)
        return self._read_receipt(request, doc_kind)

    def _classify(self, image_path: str) -> str:
        try:
            return str(self._classifier.classify(image_path) or '')
        except Exception:
            return ''

    def _read_statement(self, request: ReceiptReadRequest, doc_kind: str,
                        reread_after: str = '') -> ReceiptReadResponse:
        breakup: StatementBreakupResponse = self._statements.break_up(
            StatementBreakupRequest(
                image_path=request.image_path,
                bank_name=request.bank_name,
                account_last4=request.account_last4,
                engine=request.model,
            ))
        payload = breakup.to_http()
        return ReceiptReadResponse(
            ok=bool(payload.get('ok') or payload.get('needs_statement_metadata')),
            shape=SHAPE_MANY_EXPENSES,
            intent=ReceiptReadIntent.SEVERAL_EXPENSES,
            model=request.model,
            doc_kind=doc_kind,
            statement=payload,
            error=payload.get('error'),
            reread_after=reread_after,
        )

    def _read_receipt(self, request: ReceiptReadRequest,
                      doc_kind: str) -> ReceiptReadResponse:
        ok, payload = self._receipts.read(request.image_path, request.model)
        prefill = dict(payload or {})
        outcome = ReceiptReadOutcome.from_reader(ok, prefill)
        if outcome.warrants_statement_retry:
            statement = self._read_statement(
                request, doc_kind, reread_after=outcome.best_error)
            if _carries_transactions(statement):
                return statement
        return ReceiptReadResponse(
            ok=bool(ok),
            shape=SHAPE_ONE_EXPENSE,
            intent=ReceiptReadIntent.SEVERAL_EXPENSES,
            model=request.model,
            doc_kind=doc_kind,
            receipt={'ok': bool(ok), **prefill},
            error=outcome.best_error or None,
        )


class ReceiptReadService:
    """Context selecting an injected strategy by declared intent."""

    def __init__(self, strategies: Mapping[ReceiptReadIntent, IReceiptReadStrategy]):
        self._strategies = dict(strategies)
        missing = set(ReceiptReadIntent) - set(self._strategies)
        if missing:
            raise ValueError(f'missing receipt-read strategies: {sorted(missing)}')

    def read(self, request: ReceiptReadRequest) -> ReceiptReadResponse:
        return self._strategies[request.intent].read(request)

