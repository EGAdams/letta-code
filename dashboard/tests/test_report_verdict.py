"""The independent second opinion behind a report tab's colour."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance.report_verdict import (  # noqa: E402
    AuditorReportVerdictSource,
    NullReportVerdictSource,
    worst_status,
)


def test_worst_status_picks_the_most_severe():
    assert worst_status('pass', 'fail') == 'fail'
    assert worst_status('review', 'pass') == 'review'
    assert worst_status('pass', 'pass') == 'pass'


def test_worst_status_ignores_unknowns():
    assert worst_status('pass', None) == 'pass'
    assert worst_status(None, None) is None
    assert worst_status('review', 'not-a-status') == 'review'


def test_null_source_has_no_opinion(tmp_path):
    assert NullReportVerdictSource().verdict(str(tmp_path / 'report.html')) is None


def _source(tmp_path, module):
    source = AuditorReportVerdictSource(lib_dir='', rol_root='', logger=lambda m: None)
    source._module = module
    return source


class _FakeAudit:
    def __init__(self, status):
        self.status = status


class _FakeAuditor:
    """Counts calls so the cache can be observed."""

    def __init__(self, status):
        self.status = status
        self.calls = 0

    def audit_report(self, path):
        self.calls += 1
        return _FakeAudit(self.status)


def _report(tmp_path, body='<html></html>'):
    p = tmp_path / 'report.html'
    p.write_text(body)
    return str(p)


def test_fail_becomes_fail(tmp_path):
    assert _source(tmp_path, _FakeAuditor('FAIL')).verdict(_report(tmp_path)) == 'fail'


def test_pass_becomes_pass(tmp_path):
    assert _source(tmp_path, _FakeAuditor('PASS')).verdict(_report(tmp_path)) == 'pass'


def test_warn_is_no_opinion(tmp_path):
    """A whole-year rollup with no PDF beside it warns every run. Treating that
    as yellow turned 13 good tabs amber and buried the six real defects."""
    assert _source(tmp_path, _FakeAuditor('WARN')).verdict(_report(tmp_path)) is None


def test_a_crashing_auditor_yields_no_opinion(tmp_path):
    class _Broken:
        def audit_report(self, path):
            raise RuntimeError('boom')

    assert _source(tmp_path, _Broken()).verdict(_report(tmp_path)) is None


def test_verdict_is_cached_until_the_report_changes(tmp_path):
    auditor = _FakeAuditor('FAIL')
    source = _source(tmp_path, auditor)
    path = _report(tmp_path)
    source.verdict(path)
    source.verdict(path)
    assert auditor.calls == 1

    os.utime(path, (1, 1))
    source.verdict(path)
    assert auditor.calls == 2


def test_a_new_pdf_beside_the_report_busts_the_cache(tmp_path):
    """The verdict depends on the source document, not just the HTML."""
    auditor = _FakeAuditor('PASS')
    source = _source(tmp_path, auditor)
    path = _report(tmp_path)
    source.verdict(path)
    (tmp_path / 'statement.pdf').write_bytes(b'%PDF-1.4')
    source.verdict(path)
    assert auditor.calls == 2
