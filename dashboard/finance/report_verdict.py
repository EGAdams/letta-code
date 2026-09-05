"""Independent verdicts for statement ``report.html`` files.

A report's hero badge is written by whoever generated the report, so it is a
*claim* about the report, not a verification of it. Colouring dashboard tabs
from the badge alone means a report that copied another statement's numbers
still shows green — which is exactly how two JetBlue reports carried Fifth
Third account 7735938's transactions for four months without anyone noticing
(2026-09-05). The auditor had been reporting FAIL on both the whole time; the
dashboard simply never asked it.

These strategies supply that second opinion. The caller combines it with the
badge and takes the worse of the two, so an independent verdict can only ever
downgrade a report, never promote one its own author flagged.
"""
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod

# Dashboard-facing status vocabulary, worst last. `_classify_report_status`
# ranks by this order when reconciling the badge with an independent verdict.
PASS = 'pass'
REVIEW = 'review'
FAIL = 'fail'

STATUS_SEVERITY = {PASS: 0, REVIEW: 1, FAIL: 2}

# audit_statement_reports.AuditResult.status -> dashboard status.
#
# WARN deliberately maps to None (no opinion) rather than to REVIEW. The
# auditor warns when it could not *confirm* something -- a whole-year rollup
# with no single source PDF beside it, a section it did not recognise -- which
# is not evidence that the report is wrong. Colouring those yellow turned 13
# perfectly good tabs amber in one pass and would have buried the six that
# actually carry defects. Only a FAIL, where the auditor read the PDF and found
# the report contradicting it, is strong enough to override the badge.
_AUDIT_STATUS_MAP = {'PASS': PASS, 'WARN': None, 'FAIL': FAIL}


def worst_status(*statuses: str | None) -> str | None:
    """Return the most severe of the given statuses, ignoring None."""
    known = [s for s in statuses if s in STATUS_SEVERITY]
    if not known:
        return None
    return max(known, key=lambda s: STATUS_SEVERITY[s])


class IReportVerdictSource(ABC):
    """Strategy: judge a report against its own source document.

    Implementations MUST NOT raise. A verdict that cannot be reached is None,
    which leaves the caller on the badge alone rather than inventing a colour.
    """

    @abstractmethod
    def verdict(self, report_file: str) -> str | None:
        """Return 'pass', 'review', 'fail', or None when unavailable."""

    def findings(self, report_file: str) -> list[str]:
        """Why the verdict came out that way, one line per problem.

        A report the auditor overrules is red while still claiming PASS inside,
        so the tab has no explanation of its own to show; these lines are it.
        Empty by default — a source with no verdict has nothing to explain.
        """
        return []


class NullReportVerdictSource(IReportVerdictSource):
    """No second opinion — the badge stands on its own.

    Used by badge-parsing tests and as the fallback when the auditor cannot be
    imported at all (a missing dependency must not black out the tab list).
    """

    def verdict(self, report_file: str) -> str | None:
        return None


class AuditorReportVerdictSource(IReportVerdictSource):
    """Run the rol_finances statement auditor and translate its verdict.

    The auditor lives outside this repo, so it is imported lazily and its
    absence is tolerated. Results are cached against a fingerprint of the
    report and every PDF beside it, so a report is re-audited exactly when one
    of its inputs changes -- roughly 0.1s per report, which is why the whole
    49-report tree can be warmed in one pass at startup.
    """

    def __init__(self, lib_dir: str, rol_root: str, logger=None):
        self._lib_dir = lib_dir
        self._rol_root = rol_root
        self._logger = logger
        self._cache: dict[str, tuple[tuple, tuple[str | None, list[str]]]] = {}
        self._module = None
        self._import_failed = False

    def _log(self, message: str) -> None:
        if self._logger is not None:
            self._logger(message)

    def _auditor(self):
        """Import audit_statement_reports once; remember failure so a missing
        pypdf costs one traceback, not one per report per page load."""
        if self._module is not None or self._import_failed:
            return self._module
        import importlib
        for d in (self._rol_root, self._lib_dir):
            if d and d not in sys.path:
                sys.path.insert(0, d)
        try:
            self._module = importlib.import_module('audit_statement_reports')
        except Exception as exc:  # pragma: no cover - environment guard
            self._import_failed = True
            self._log(f'report auditor unavailable, falling back to badge: {exc}')
        return self._module

    @staticmethod
    def _fingerprint(report_file: str) -> tuple:
        """Identify the inputs a verdict depends on: the report and the PDFs in
        its directory. Ordered so an added or removed PDF also busts the entry."""
        parts = []
        directory = os.path.dirname(report_file)
        names = [os.path.basename(report_file)]
        try:
            names += sorted(n for n in os.listdir(directory)
                            if n.lower().endswith('.pdf'))
        except OSError:
            pass
        for name in names:
            try:
                st = os.stat(os.path.join(directory, name))
                parts.append((name, st.st_mtime_ns, st.st_size))
            except OSError:
                parts.append((name, None, None))
        return tuple(parts)

    def _audit(self, report_file: str) -> tuple[str | None, list[str]]:
        """Cached (status, findings) for one report."""
        fingerprint = self._fingerprint(report_file)
        cached = self._cache.get(report_file)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]
        auditor = self._auditor()
        outcome: tuple[str | None, list[str]] = (None, [])
        if auditor is not None:
            try:
                from pathlib import Path
                audited = auditor.audit_report(Path(report_file))
                outcome = (_AUDIT_STATUS_MAP.get(audited.status),
                           list(getattr(audited, 'findings', []) or []))
            except Exception as exc:
                # A crash in the auditor is not evidence about the report.
                self._log(f'report audit failed for {report_file}: {exc}')
                outcome = (None, [])
        self._cache[report_file] = (fingerprint, outcome)
        return outcome

    def verdict(self, report_file: str) -> str | None:
        return self._audit(report_file)[0]

    def findings(self, report_file: str) -> list[str]:
        return self._audit(report_file)[1]

    def warm(self, report_files) -> int:
        """Pre-compute verdicts so the first page load is not the slow one.

        Returns the number of reports audited. Safe to call from a one-shot
        background thread at startup; it only fills the same cache `verdict`
        would fill lazily.
        """
        count = 0
        for report_file in report_files:
            self.verdict(report_file)
            count += 1
        return count
