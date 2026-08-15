"""Supporting-document slot rules, driven through a fake intake port."""

from dataclasses import dataclass

import pytest

from finance.report_page import ReportPageRoutes
from finance.supporting_documents import (
    IIntakePageLookup,
    SupportingDocumentPageResolver,
    slot_reference,
)

ROUTES = ReportPageRoutes(
    scanner_path='/scanner_report.html',
    recent_path='/recent_report.html',
)


class FakeIntakeLookup(IIntakePageLookup):
    """In-memory stand-in for the server's intake state."""

    def __init__(self, recent=None, scanners=None):
        self._recent = recent or {}
        self._scanners = scanners or {}
        self.scanner_calls = []

    def recent_report(self):
        return self._recent

    def scanner_intake(self, scanner_key):
        self.scanner_calls.append(scanner_key)
        return self._scanners.get(scanner_key, {})

    def intake_scan_reference(self, intake):
        return str(intake.get('image_path') or '')


def _resolver(**kwargs):
    return SupportingDocumentPageResolver(FakeIntakeLookup(**kwargs), ROUTES)


class TestScannedStatementReference:
    def test_a_scanner_page_offers_its_own_statement_scan(self):
        resolver = _resolver(
            scanners={'window': {'doc_kind': 'statement',
                                 'image_path': '/scans/window.jpg'}}
        )
        assert resolver.scanned_statement_reference(
            '/scanner_report.html?scanner=window'
        ) == '/scans/window.jpg'

    @pytest.mark.parametrize('doc_kind', ['receipt', 'invoice', 'RECEIPT'])
    def test_a_receipt_or_invoice_scan_is_not_a_statement(self, doc_kind):
        resolver = _resolver(
            scanners={'window': {'doc_kind': doc_kind,
                                 'image_path': '/scans/window.jpg'}}
        )
        assert resolver.scanned_statement_reference(
            '/scanner_report.html?scanner=window'
        ) == ''

    def test_an_unclassified_scan_still_counts(self):
        """`doc_kind` is seeded 'unknown' until Mazda classifies the image."""
        resolver = _resolver(
            scanners={'window': {'doc_kind': 'unknown',
                                 'image_path': '/scans/window.jpg'}}
        )
        assert resolver.scanned_statement_reference(
            '/scanner_report.html?scanner=window'
        ) == '/scans/window.jpg'

    def test_recent_report_in_intake_mode_offers_the_dispatched_scan(self):
        resolver = _resolver(
            recent={'mode': 'intake',
                    'intake': {'doc_kind': 'statement',
                               'image_path': '/scans/recent.jpg'}}
        )
        assert resolver.scanned_statement_reference(
            '/recent_report.html'
        ) == '/scans/recent.jpg'

    def test_a_real_month_report_has_no_page_scan_to_offer(self):
        resolver = _resolver()
        assert resolver.scanned_statement_reference(
            '/rol_finances_reports/2025/july/report.html'
        ) == ''

    def test_one_scanner_never_borrows_the_other_scanner(self):
        lookup = FakeIntakeLookup(
            scanners={'window': {'doc_kind': 'statement',
                                 'image_path': '/scans/window.jpg'}}
        )
        resolver = SupportingDocumentPageResolver(lookup, ROUTES)
        assert resolver.scanned_statement_reference(
            '/scanner_report.html?scanner=freezer'
        ) == ''
        assert lookup.scanner_calls == ['freezer']


class TestSourceDocumentReference:
    def test_a_synthetic_scanner_page_offers_no_downloaded_source(self):
        resolver = _resolver(
            scanners={'window': {'doc_kind': 'statement',
                                 'image_path': '/scans/window.jpg'}}
        )
        assert resolver.source_document_reference(
            '/scanner_report.html?scanner=window',
            lambda path: '/should/not/be/used.pdf',
        ) == ''

    def test_recent_report_backed_by_a_report_resolves_that_report(self):
        resolver = _resolver(
            recent={'mode': 'report', 'url': '/reports/july/report.html'}
        )
        seen = []

        def resolve(path):
            seen.append(path)
            return '/reports/july/statement.pdf'

        assert resolver.source_document_reference(
            '/recent_report.html', resolve
        ) == '/reports/july/statement.pdf'
        assert seen == ['/reports/july/report.html']

    def test_a_month_report_resolves_beside_itself(self):
        resolver = _resolver()
        assert resolver.source_document_reference(
            '/reports/july/report.html', lambda path: f'{path}::source'
        ) == '/reports/july/report.html::source'


@dataclass(frozen=True)
class Slot:
    kind: str
    expense_field: str
    falls_back_to_page_scan: bool


class TestSlotReference:
    SCANNED = Slot('scanned_statement', 'scanned_statement_url', True)
    RECEIPT = Slot('receipt', 'receipt_url', False)

    def test_a_stored_reference_always_wins(self):
        assert slot_reference(
            {'scanned_statement_url': '/stored.jpg'}, self.SCANNED, '/page',
            normalize=lambda v: str(v or ''),
            page_scan=lambda path: '/page-scan.jpg',
        ) == '/stored.jpg'

    def test_an_empty_slot_falls_back_only_when_the_catalog_allows_it(self):
        assert slot_reference(
            {}, self.SCANNED, '/page',
            normalize=lambda v: str(v or ''),
            page_scan=lambda path: '/page-scan.jpg',
        ) == '/page-scan.jpg'
        assert slot_reference(
            {}, self.RECEIPT, '/page',
            normalize=lambda v: str(v or ''),
            page_scan=lambda path: '/page-scan.jpg',
        ) == ''

    def test_a_missing_row_is_not_an_error(self):
        assert slot_reference(
            None, self.RECEIPT, '/page',
            normalize=lambda v: str(v or ''),
            page_scan=lambda path: '',
        ) == ''
