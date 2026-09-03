"""Small runtime schemas for bounded receipt-prefill model output."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FocusedReceiptReading(BaseModel):
    model_config = ConfigDict(extra='forbid')

    merchant_name: Optional[str] = None
    transaction_date: Optional[date] = None
    total_amount: Optional[float] = None
    has_marked_items: bool = False
    selection_evidence: Optional[str] = None

    def to_prefill(self) -> dict:
        return {
            'merchant_name': self.merchant_name,
            'transaction_date': (
                self.transaction_date.isoformat()
                if self.transaction_date else None),
            'total_amount': self.total_amount,
            'selection_evidence': self.selection_evidence,
        }


FOCUSED_RECEIPT_JSON_SCHEMA = FocusedReceiptReading.model_json_schema()

# Gemini's generateContent structured-output field accepts a documented
# subset of JSON Schema. Keep this transport schema explicit rather than
# sending Pydantic's richer anyOf/default vocabulary across that boundary.
GEMINI_FOCUSED_SCHEMA = {
    'type': 'object',
    'properties': {
        'merchant_name': {'type': 'string', 'nullable': True},
        'transaction_date': {
            'type': 'string', 'format': 'date', 'nullable': True},
        'total_amount': {'type': 'number', 'nullable': True},
        'has_marked_items': {'type': 'boolean'},
        'selection_evidence': {'type': 'string', 'nullable': True},
    },
    'required': [
        'merchant_name',
        'transaction_date',
        'total_amount',
        'has_marked_items',
        'selection_evidence',
    ],
}
