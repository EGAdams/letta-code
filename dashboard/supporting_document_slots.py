"""Catalog for supporting-document fields exposed by the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SupportingDocumentSlot:
    kind: str
    expense_field: str
    label: str
    #: When the row stores nothing, may the page's own intake scan stand in?
    #: True only for the scanned-statement slot: a synthetic scanner page knows
    #: which paper image its rows came from, and legacy rows predate the column.
    falls_back_to_page_scan: bool = False


def _normalize_supporting_document_target(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("id", "document_id", "source_document_id", "receipt_id", "value", "target"):
            if key in value and value[key] is not None:
                return _normalize_supporting_document_target(value[key])
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_supporting_document_target(item)
            if normalized:
                return normalized
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    for prefix in ("receipt:", "receipt ", "source_document:", "source document:", "document:", "supporting_document:"):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):].strip()
            break
    return lowered


class SupportingDocumentCatalog:
    _slots = (
        SupportingDocumentSlot("receipt", "receipt_url", "View Receipt"),
        SupportingDocumentSlot("source", "document_url", "View Source Document"),
        SupportingDocumentSlot(
            "scanned_statement",
            "scanned_statement_url",
            "View Scanned Statement",
            falls_back_to_page_scan=True,
        ),
        SupportingDocumentSlot("moms_ledger", "moms_ledger", "View Mom’s Ledger"),
    )

    def slots(self):
        return self._slots

    def slot_for_kind(self, kind):
        return next((slot for slot in self._slots if slot.kind == kind), None)

    def fields(self):
        return tuple(slot.expense_field for slot in self._slots)


def get_supporting_document_lookup_key(
    document: Mapping[str, Any] | None,
    *,
    kind: str,
) -> str:
    if not document:
        return ""
    if kind == "receipt":
        candidate = document.get("receipt_id") or document.get("id") or document.get("document_id")
        return _normalize_supporting_document_target(candidate)

    source_candidate = document.get("source_document_id") or document.get("source_document")
    source_key = _normalize_supporting_document_target(source_candidate)
    if source_key:
        return source_key

    candidate = document.get("id") or document.get("document_id")
    return _normalize_supporting_document_target(candidate)


SUPPORTING_DOCUMENT_CATALOG = SupportingDocumentCatalog()
