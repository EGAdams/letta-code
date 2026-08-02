"""Catalog for supporting-document fields exposed by the dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportingDocumentSlot:
    kind: str
    expense_field: str
    label: str


class SupportingDocumentCatalog:
    _slots = (
        SupportingDocumentSlot("receipt", "receipt_url", "View Receipt"),
        SupportingDocumentSlot("source", "document_url", "View Source Document"),
        SupportingDocumentSlot(
            "scanned_statement",
            "scanned_statement_url",
            "View Scanned Statement",
        ),
        SupportingDocumentSlot("moms_ledger", "moms_ledger", "View Mom’s Ledger"),
    )

    def slots(self):
        return self._slots

    def slot_for_kind(self, kind):
        return next((slot for slot in self._slots if slot.kind == kind), None)

    def fields(self):
        return tuple(slot.expense_field for slot in self._slots)


SUPPORTING_DOCUMENT_CATALOG = SupportingDocumentCatalog()
