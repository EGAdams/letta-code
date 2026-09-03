"""Synchronize an edited expense's receipt identity and stored references."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

from contracts import StrictModel
from finance.archive_path import build_id_light, vendor_prefix_from_id_light
from finance.expense_edit_model import (
    ExpenseEdit,
    ExpenseRecord,
    linkage_warnings,
)
from finance.receipt_relocation import IReceiptFileRelocator


class ReceiptEditReferences(StrictModel):
    """Validated database values produced by one receipt-file synchronization."""

    id_light: str = ''
    receipt_url: str = ''
    document_url: str = ''
    source_file: str = ''
    warnings: tuple[str, ...] = ()


class IExpenseReceiptSynchronizer(ABC):
    """Bridge between an expense edit and the receipt filesystem strategy."""

    @abstractmethod
    def synchronize(self, before: ExpenseRecord, edit: ExpenseEdit,
                    changed: tuple[str, ...]) -> ReceiptEditReferences:
        """Return only references that must replace stored values."""


def _same_receipt(reference: str, receipt_url: str) -> bool:
    return bool(reference and receipt_url and
                os.path.basename(reference) == os.path.basename(receipt_url))


class ExpenseReceiptSynchronizer(IExpenseReceiptSynchronizer):
    """Coordinate filing-key changes through an injected file relocator."""

    def __init__(self, relocator: IReceiptFileRelocator):
        self._relocator = relocator

    def synchronize(self, before, edit, changed):
        if not before.id_light or not before.receipt_url:
            return ReceiptEditReferences(warnings=linkage_warnings(before, changed))
        if not any(field in changed for field in ('expense_date', 'amount')):
            return ReceiptEditReferences()

        new_id_light = build_id_light(
            vendor_prefix_from_id_light(before.id_light),
            edit.transaction_date,
            edit.total_amount,
        )
        relocated = self._relocator.relocate(
            receipt_url=before.receipt_url,
            old_id_light=before.id_light,
            new_id_light=new_id_light,
        )
        if not relocated.relocated:
            warnings = (relocated.warning,) if relocated.warning else ()
            return ReceiptEditReferences(warnings=warnings)

        document_url = ''
        if _same_receipt(before.document_url, before.receipt_url):
            document_url = (relocated.new_path if os.path.isabs(before.document_url)
                            else relocated.new_receipt_url)
        source_file = ''
        if _same_receipt(before.source_file, before.receipt_url):
            source_file = relocated.new_path
        return ReceiptEditReferences(
            id_light=new_id_light,
            receipt_url=relocated.new_receipt_url,
            document_url=document_url,
            source_file=source_file,
        )
