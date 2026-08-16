"""What kind of report page a supporting-document row is being viewed on.

The dashboard shows expense rows on four different pages, and which documents
a row may offer depends on which one. That question used to be re-answered by
string-parsing the report URL inside every resolver, so the rules drifted
apart. Parse once, into a typed page, and let the page answer.
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote

from contracts import StrictModel


class ReportPageRoutes(StrictModel):
    """The two synthetic routes, injected rather than imported from server."""

    scanner_path: str
    recent_path: str


class ScannerReportPage(StrictModel):
    """A per-scanner page built live from the DB. No downloaded source."""

    scanner_key: str = ''
    has_downloaded_source: bool = False
    has_intake_scan: bool = True


class RecentIntakePage(StrictModel):
    """Recent Report rendered from an intake record, not a report.html."""

    has_downloaded_source: bool = False
    has_intake_scan: bool = True


class RecentReportPage(StrictModel):
    """Recent Report pointing at a real report.html."""

    report_url: str = ''
    has_downloaded_source: bool = True
    has_intake_scan: bool = False


class MonthReportPage(StrictModel):
    """A statement's own month report, living beside its source document."""

    report_path: str = ''
    has_downloaded_source: bool = True
    has_intake_scan: bool = False


ReportPage = (
    ScannerReportPage | RecentIntakePage | RecentReportPage | MonthReportPage
)


def parse_report_page(
    report_path: str,
    routes: ReportPageRoutes,
    *,
    recent_mode: str = '',
    recent_url: str = '',
) -> ReportPage:
    """Identify the page a row is displayed on.

    `recent_mode`/`recent_url` are supplied by the caller (which owns the
    recent-report pointer) so this stays a pure function.
    """
    base, _, query = unquote(str(report_path or '')).partition('?')
    if base == routes.scanner_path:
        scanner_key = (parse_qs(query).get('scanner', [''])[0] or '').strip().lower()
        return ScannerReportPage(scanner_key=scanner_key)
    if base == routes.recent_path:
        if recent_mode == 'intake':
            return RecentIntakePage()
        return RecentReportPage(report_url=str(recent_url or ''))
    return MonthReportPage(report_path=str(report_path or ''))


class ReportRowMatch(StrictModel):
    """One <tr> found by scanning every report.html for a (date, amount).

    Replaces the plain dict _find_matching_report_row used to return: a typed
    boundary makes a missing/renamed key a load-time AttributeError instead of
    a silent None spreading through recategorization and source-document
    lookups.
    """

    report_path: str
    label: str
    row_vendor_key: str


#: Intake kinds whose scan is the receipt itself, not a statement page.
NON_STATEMENT_INTAKE_KINDS = frozenset({'receipt', 'invoice'})


def intake_supplies_a_scanned_statement(doc_kind: str) -> bool:
    """A receipt/invoice scan is not scanned-statement evidence."""
    return str(doc_kind or '').strip().lower() not in NON_STATEMENT_INTAKE_KINDS
