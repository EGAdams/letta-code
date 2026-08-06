"""Typed application boundary for expense supporting documents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
import re
from typing import Any
from urllib.parse import quote, urlparse

from pydantic import BaseModel, ConfigDict, Field

from supporting_document_slots import SupportingDocumentCatalog


class StrictBoundaryModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class SupportingDocumentRequest(StrictBoundaryModel):
    date: str = ""
    signed_amount: str = ""
    vendor_key: str = ""
    document_type: str = ""
    description: str = ""
    expense_id: int | None = None
    report_path: str = ""


class SupportingDocumentDescriptor(StrictBoundaryModel):
    type: str
    label: str
    field: str = ""
    available: bool


class SupportingDocumentLookupResponse(StrictBoundaryModel):
    ok: bool
    expense_id: int | None = None
    receipt_url: str | None = None
    document_url: str | None = None
    scanned_statement_url: str | None = None
    moms_ledger: str | None = None
    notes: str = ""
    documents: list[SupportingDocumentDescriptor] = Field(default_factory=list)
    error: str | None = None


class SupportingDocumentOpenResponse(StrictBoundaryModel):
    ok: bool
    url: str | None = None
    highlighted: bool = False
    highlight_note: str | None = None
    error: str | None = None


class SupportingDocumentPorts:
    """Narrow callbacks supplied by the dashboard composition root."""

    def __init__(
        self,
        *,
        lookup_expense: Callable[..., Mapping[str, Any] | None],
        normalize_amount: Callable[[object], str | None],
        catalog: SupportingDocumentCatalog,
        normalize_reference: Callable[[object], str],
        usable_reference: Callable[[object], bool],
        resolve_local: Callable[[str, str], str | None],
        viewable: Callable[[str, str | None], bool],
        source_reference: Callable[[Mapping[str, Any] | None, str], str],
        prepare_view: Callable[[Mapping[str, Any], str, str], Any],
        document_url_prefix: str,
        reference_for: Callable[[Mapping[str, Any] | None, str, str], str] | None = None,
        describe_documents: Callable[[Mapping[str, Any], str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.lookup_expense = lookup_expense
        self.normalize_amount = normalize_amount
        self.catalog = catalog
        self.normalize_reference = normalize_reference
        self.usable_reference = usable_reference
        self.resolve_local = resolve_local
        self.viewable = viewable
        self.source_reference = source_reference
        self.reference_for = reference_for
        self.prepare_view = prepare_view
        self.document_url_prefix = document_url_prefix
        self.describe_documents = describe_documents


class ISupportingDocumentService(ABC):
    @abstractmethod
    def lookup(self, request: SupportingDocumentRequest) -> SupportingDocumentLookupResponse:
        pass

    @abstractmethod
    def open(self, request: SupportingDocumentRequest) -> SupportingDocumentOpenResponse:
        pass

    @abstractmethod
    def path_for_expense(self, expense_id: int, document_type: str, report_path: str = "") -> str | None:
        pass

    @abstractmethod
    def view_for_expense(self, expense_id: int, document_type: str, report_path: str = "") -> str | None:
        pass


class SupportingDocumentService(ISupportingDocumentService):
    """Supporting-document use cases composed entirely from injected ports."""

    def __init__(self, ports: SupportingDocumentPorts) -> None:
        self._ports = ports

    def _find(self, request: SupportingDocumentRequest):
        amount = self._ports.normalize_amount(request.signed_amount)
        if amount is None and request.expense_id is None:
            return None
        return self._ports.lookup_expense(
            request.date, request.signed_amount, request.vendor_key,
            request.description, request.expense_id,
        )

    def _descriptors(self, chosen, report_path: str):
        if self._ports.describe_documents is not None:
            return [SupportingDocumentDescriptor(**item)
                    for item in self._ports.describe_documents(chosen, report_path)]
        descriptors = []
        for slot in self._ports.catalog.slots():
            kind, label, field = slot.kind, slot.label, slot.expense_field
            reference = self._reference_for(chosen, kind, report_path)[0]
            local_path = self._ports.resolve_local(reference, kind)
            remote_url = urlparse(reference).scheme in {"http", "https"}
            descriptors.append(SupportingDocumentDescriptor(
                type=kind, label=label, field=field,
                available=(self._ports.usable_reference(reference)
                           and bool(local_path or remote_url)
                           and self._ports.viewable(reference, local_path)),
            ))
        return descriptors

    def descriptors(self, chosen: Mapping[str, Any], report_path: str = ""):
        """Return typed descriptors for callers that already selected a row."""
        return self._descriptors(chosen, report_path)

    def _reference_for(self, chosen, document_type: str, report_path: str):
        slot = self._ports.catalog.slot_for_kind(document_type)
        if not slot or not chosen:
            return "", False
        stored_reference = self._ports.normalize_reference(
            chosen.get(slot.expense_field)
        )
        if self._ports.reference_for is not None:
            reference = self._ports.reference_for(chosen, document_type, report_path)
        elif document_type == "source":
            reference = self._ports.source_reference(chosen, report_path)
        else:
            reference = stored_reference
        return reference, bool(reference) and reference != stored_reference

    def lookup(self, request: SupportingDocumentRequest, *,
               descriptor_builder: Callable[[Mapping[str, Any], str], list[dict[str, Any]]] | None = None):
        try:
            chosen = self._find(request)
        except Exception as exc:
            return SupportingDocumentLookupResponse(ok=False, error=f"DB error: {exc}")
        if not chosen:
            return SupportingDocumentLookupResponse(ok=False, error="No matching expense in DB.")
        return SupportingDocumentLookupResponse(
            ok=True, expense_id=int(chosen["id"]),
            receipt_url=chosen.get("receipt_url"), document_url=chosen.get("document_url"),
            scanned_statement_url=chosen.get("scanned_statement_url"),
            moms_ledger=chosen.get("moms_ledger"), notes=chosen.get("notes") or "",
            documents=(
                [SupportingDocumentDescriptor(**item)
                 for item in descriptor_builder(chosen, request.report_path)]
                if descriptor_builder is not None
                else self._descriptors(chosen, request.report_path)
            ),
        )

    def open(self, request: SupportingDocumentRequest):
        slot = self._ports.catalog.slot_for_kind(request.document_type)
        if not slot:
            return SupportingDocumentOpenResponse(ok=False, error="Unknown supporting-document type.")
        try:
            chosen = self._find(request)
        except Exception as exc:
            return SupportingDocumentOpenResponse(ok=False, error=f"DB error: {exc}")
        reference, source_from_report = self._reference_for(chosen, request.document_type, request.report_path)
        if not self._ports.usable_reference(reference):
            return SupportingDocumentOpenResponse(ok=False, error=f"{request.document_type} document is not on file.")
        parsed = urlparse(reference)
        if parsed.scheme in {"http", "https"}:
            if not self._ports.viewable(reference, None):
                return SupportingDocumentOpenResponse(ok=False, error=self._not_viewable_error(request.document_type))
            return SupportingDocumentOpenResponse(ok=True, url=reference,
                highlight_note="Remote documents are opened without a local annotation.")
        path = self._ports.resolve_local(reference, request.document_type)
        if not path:
            print(f"[supporting-document] missing type={request.document_type} expense_id={chosen.get('id') if chosen else ''}")
            return SupportingDocumentOpenResponse(ok=False, error=self._not_found_error(request.document_type))
        if not self._ports.viewable(reference, path):
            return SupportingDocumentOpenResponse(ok=False, error=self._not_viewable_error(request.document_type))
        prepared = self._ports.prepare_view(chosen or {}, path, request.document_type)
        fragment = parsed.fragment
        if prepared.highlighted and prepared.page:
            fragment = f"page={prepared.page}"
        page_fragment = f"#{fragment}" if re.fullmatch(r"page=[1-9][0-9]*", fragment or "") else ""
        viewer_url = f"{self._ports.document_url_prefix}/{int(chosen['id'])}/{request.document_type}"
        if source_from_report:
            viewer_url += f"?report_path={quote(request.report_path, safe='')}"
        return SupportingDocumentOpenResponse(ok=True, url=viewer_url + page_fragment,
            highlighted=prepared.highlighted, highlight_note=prepared.reason)

    def path_for_expense(self, expense_id: int, document_type: str, report_path: str = ""):
        if not self._ports.catalog.slot_for_kind(document_type):
            return None
        try:
            chosen = self._ports.lookup_expense("", "", "", "", expense_id=int(expense_id))
        except (TypeError, ValueError, LookupError):
            return None
        except Exception as exc:
            print(f"[supporting-document] lookup failed expense_id={expense_id} type={document_type}: {exc}")
            return None
        reference, _ = self._reference_for(chosen, document_type, report_path)
        if not self._ports.usable_reference(reference):
            return None
        path = self._ports.resolve_local(reference, document_type)
        return path if path and self._ports.viewable(reference, path) else None

    def view_for_expense(self, expense_id: int, document_type: str, report_path: str = ""):
        try:
            chosen = self._ports.lookup_expense("", "", "", "", expense_id=int(expense_id))
        except (TypeError, ValueError, LookupError):
            return None
        except Exception as exc:
            print(f"[supporting-document] viewer lookup failed expense_id={expense_id} type={document_type}: {exc}")
            return None
        source_path = self.path_for_expense(expense_id, document_type, report_path)
        if not chosen or not source_path:
            return None
        result = self._ports.prepare_view(chosen, source_path, document_type)
        if not result.highlighted:
            print(f"[supporting-document] opened without highlight expense_id={expense_id} type={document_type} reason={result.reason}")
        return result.path

    @staticmethod
    def _not_viewable_error(document_type: str) -> str:
        return f"The {document_type.replace('_', ' ')} reference is not a viewable PDF, image, or Excel workbook."

    @staticmethod
    def _not_found_error(document_type: str) -> str:
        return f"The {document_type.replace('_', ' ')} document could not be found."
