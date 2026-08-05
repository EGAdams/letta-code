"""Contract tests for report-page identity.

Which supporting documents a row can offer depends on what kind of page the
row is being viewed on. That was decided by re-parsing the report URL inside
each resolver; here it is parsed once into a typed page.
"""

import pytest
from pydantic import ValidationError

from finance.report_page import (
    MonthReportPage,
    RecentIntakePage,
    RecentReportPage,
    ReportPageRoutes,
    ScannerReportPage,
    parse_report_page,
)

ROUTES = ReportPageRoutes(
    scanner_path='/scanner_report.html',
    recent_path='/recent_report.html',
)


def _parse(path, *, recent_is_intake=False, recent_url=''):
    return parse_report_page(
        path,
        ROUTES,
        recent_mode='intake' if recent_is_intake else 'report',
        recent_url=recent_url,
    )


class TestParsing:
    def test_a_scanner_page_carries_its_scanner_key(self):
        page = _parse('/scanner_report.html?scanner=Window')
        assert isinstance(page, ScannerReportPage)
        assert page.scanner_key == 'window'

    def test_a_scanner_page_without_a_scanner_still_parses(self):
        page = _parse('/scanner_report.html')
        assert isinstance(page, ScannerReportPage)
        assert page.scanner_key == ''

    def test_recent_report_in_intake_mode_is_its_own_kind(self):
        page = _parse('/recent_report.html', recent_is_intake=True)
        assert isinstance(page, RecentIntakePage)

    def test_recent_report_backed_by_a_real_report_resolves_that_url(self):
        page = _parse(
            '/recent_report.html', recent_url='/reports/july/report.html'
        )
        assert isinstance(page, RecentReportPage)
        assert page.report_url == '/reports/july/report.html'

    def test_any_other_path_is_a_month_report(self):
        page = _parse('/rol_finances_reports/2025/july/report.html')
        assert isinstance(page, MonthReportPage)
        assert page.report_path == '/rol_finances_reports/2025/july/report.html'

    def test_a_percent_encoded_path_is_decoded_before_routing(self):
        page = _parse('/scanner_report.html%3Fscanner%3Dfreezer')
        assert isinstance(page, ScannerReportPage)
        assert page.scanner_key == 'freezer'

    def test_an_empty_path_is_a_month_report_with_no_path(self):
        page = _parse('')
        assert isinstance(page, MonthReportPage)
        assert page.report_path == ''


class TestPageCapabilities:
    """A synthetic DB-backed page has no downloaded source document.

    Its paper scan belongs to the scanned-statement slot, never to the
    downloaded-source slot — conflating the two is what made a scanner report
    offer a missing image as a source document.
    """

    @pytest.mark.parametrize(
        'page,expected',
        [
            (ScannerReportPage(scanner_key='window'), False),
            (RecentIntakePage(), False),
            (RecentReportPage(report_url='/x/report.html'), True),
            (MonthReportPage(report_path='/x/report.html'), True),
        ],
    )
    def test_only_real_report_pages_have_a_downloaded_source(self, page, expected):
        assert page.has_downloaded_source is expected

    @pytest.mark.parametrize(
        'page,expected',
        [
            (ScannerReportPage(scanner_key='window'), True),
            (RecentIntakePage(), True),
            (RecentReportPage(report_url='/x/report.html'), False),
            (MonthReportPage(report_path='/x/report.html'), False),
        ],
    )
    def test_only_intake_pages_can_supply_their_own_scan(self, page, expected):
        assert page.has_intake_scan is expected


class TestStrictness:
    def test_pages_are_strict_frozen_models(self):
        with pytest.raises(ValidationError):
            ScannerReportPage(scanner_key='window', extra='nope')
        with pytest.raises(ValidationError):
            ScannerReportPage(scanner_key=None)
        page = ScannerReportPage(scanner_key='window')
        with pytest.raises(ValidationError):
            page.scanner_key = 'freezer'
