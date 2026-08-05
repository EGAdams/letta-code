"""Which supporting document a row offers, per slot and per page.

Holds the rules that decide a slot's reference. Everything it needs from the
running server — the recent-report pointer, a scanner's intake record, and how
an intake names its scan — arrives through `IIntakePageLookup`, so the rules
are testable with no server, no filesystem, and no database.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping

from finance.report_page import (
    RecentIntakePage,
    RecentReportPage,
    ReportPage,
    ReportPageRoutes,
    ScannerReportPage,
    intake_supplies_a_scanned_statement,
    parse_report_page,
)


class IIntakePageLookup(ABC):
    """Port: the intake state behind the dashboard's synthetic report pages."""

    @abstractmethod
    def recent_report(self) -> Mapping[str, Any]:
        """The current recent-report pointer, or an empty mapping."""

    @abstractmethod
    def scanner_intake(self, scanner_key: str) -> Mapping[str, Any]:
        """The last intake record for one scanner, or an empty mapping."""

    @abstractmethod
    def intake_scan_reference(self, intake: Mapping[str, Any]) -> str:
        """The stored image reference an intake record points at."""


class SupportingDocumentPageResolver:
    """Resolves page identity and the page-supplied scanned statement."""

    def __init__(self, lookup: IIntakePageLookup, routes: ReportPageRoutes):
        self._lookup = lookup
        self._routes = routes

    def page_for(self, report_path: str) -> ReportPage:
        recent = self._lookup.recent_report() or {}
        return parse_report_page(
            report_path,
            self._routes,
            recent_mode=str(recent.get('mode') or ''),
            recent_url=str(recent.get('url') or ''),
        )

    def intake_for(self, page: ReportPage) -> Mapping[str, Any]:
        if isinstance(page, ScannerReportPage):
            return self._lookup.scanner_intake(page.scanner_key) or {}
        if isinstance(page, RecentIntakePage):
            return (self._lookup.recent_report() or {}).get('intake') or {}
        return {}

    def scanned_statement_reference(self, report_path: str) -> str:
        """The page's own paper scan, when the row itself stores none.

        A scanner page has no downloaded source document; if the expense row
        predates `scanned_statement_url`, the page's immutable intake image is
        still the correct evidence — unless the intake was a receipt or
        invoice, which is not a statement at all.
        """
        page = self.page_for(report_path)
        if not page.has_intake_scan:
            return ''
        intake = self.intake_for(page)
        if not intake_supplies_a_scanned_statement(intake.get('doc_kind')):
            return ''
        return self._lookup.intake_scan_reference(intake)

    def source_document_reference(
        self,
        report_path: str,
        resolve_report_source: Callable[[str], str],
    ) -> str:
        """The downloaded source document the page itself can offer.

        Synthetic DB-backed pages have none: their paper scan belongs to the
        scanned-statement slot, never to this one.
        """
        page = self.page_for(report_path)
        if not page.has_downloaded_source:
            return ''
        if isinstance(page, RecentReportPage):
            return resolve_report_source(page.report_url)
        return resolve_report_source(report_path)


def slot_reference(
    chosen: Mapping[str, Any] | None,
    slot: Any,
    report_path: str,
    *,
    normalize: Callable[[Any], str],
    page_scan: Callable[[str], str],
) -> str:
    """One slot's reference, including its page fallback.

    The single place the fallback lives: previously each of the three call
    sites re-implemented it, so a fourth slot meant finding every site again.
    """
    reference = normalize((chosen or {}).get(slot.expense_field))
    if reference or not slot.falls_back_to_page_scan:
        return reference
    return page_scan(report_path)
