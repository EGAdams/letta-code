"""Typed agreements for the manual receipt-reading actions.

The browser chooses *what work is needed*.  The composition root chooses the
object that performs that work.  Keeping those two decisions separate lets a
fast three-field reader and the forensic parser remain interchangeable at the
HTTP boundary without pretending they do the same amount of work.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from typing import Any, Optional

from pydantic import field_validator

from finance.manual_entry import PREVIEW_ENGINES
from finance.statement_models import STATEMENT_ENGINES, StrictBoundaryModel


RECEIPT_READ_MODELS: dict[str, str] = {
    'gemini-only': 'Gemini Flash',
    'haiku-only': 'Claude Haiku',
    'codex-only': 'Codex (luna)',
}
DEFAULT_RECEIPT_READ_MODEL = 'gemini-only'

SHAPE_ONE_EXPENSE = 'one-expense'
SHAPE_MANY_EXPENSES = 'many-expenses'


class ReceiptReadIntent(str, Enum):
    CIRCLED_ONLY = 'circled-only'
    TOTAL_ONLY = 'total-only'
    SEVERAL_EXPENSES = 'several-expenses'


def assert_models_are_supported() -> None:
    unsupported = sorted(
        set(RECEIPT_READ_MODELS)
        - (set(PREVIEW_ENGINES) & set(STATEMENT_ENGINES)))
    if unsupported:
        raise RuntimeError(
            'RECEIPT_READ_MODELS contains models a reader rejects: '
            f'{unsupported}')


assert_models_are_supported()


class ReceiptReadRequest(StrictBoundaryModel):
    image_path: str
    intent: ReceiptReadIntent
    model: str = DEFAULT_RECEIPT_READ_MODEL
    bank_name: str = ''
    account_last4: str = ''

    @field_validator('image_path')
    @classmethod
    def _image_path_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('image_path is required')
        return value

    @field_validator('model')
    @classmethod
    def _known_model(cls, value: str) -> str:
        if value not in RECEIPT_READ_MODELS:
            raise ValueError(
                f'model must be one of {sorted(RECEIPT_READ_MODELS)}')
        return value

    @classmethod
    def from_http(cls, data: Mapping[str, Any] | None) -> 'ReceiptReadRequest':
        data = data or {}
        intent_value = str(data.get('intent') or '').strip()
        return cls(
            image_path=str(data.get('image_path') or '').strip(),
            intent=ReceiptReadIntent(intent_value),
            model=str(data.get('model') or DEFAULT_RECEIPT_READ_MODEL).strip(),
            bank_name=' '.join(str(data.get('bank_name') or '').split()),
            account_last4=str(data.get('account_last4') or '').strip(),
        )


class ReceiptReadResponse(StrictBoundaryModel):
    ok: bool
    shape: str
    intent: ReceiptReadIntent
    model: str
    doc_kind: str = ''
    receipt: Optional[dict] = None
    statement: Optional[dict] = None
    reread_after: str = ''
    error: Optional[str] = None

    def to_http(self) -> dict:
        return self.model_dump(mode='json')


class IReceiptReadStrategy(ABC):
    """One interchangeable interpretation of a receipt-read request."""

    @abstractmethod
    def read(self, request: ReceiptReadRequest) -> ReceiptReadResponse:
        ...


class IFocusedReceiptReader(ABC):
    """Port for a bounded receipt read that returns one expense total."""

    @abstractmethod
    def read(self, image_path: str, model: str,
             intent: ReceiptReadIntent) -> tuple[bool, Mapping[str, Any]]:
        ...
