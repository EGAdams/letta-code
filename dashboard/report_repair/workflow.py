"""One-at-a-time repair loop with explicit 90% confidence boundaries."""

from __future__ import annotations

import calendar
from pathlib import PurePosixPath
from time import monotonic
from typing import Callable

from report_repair.api import DashboardApi
from report_repair.dialogs import show_blocker
from report_repair.models import Blocker, MonthStatus, RepairTarget
from report_repair.navigator import ReportsNavigator
from report_repair.policy import recommend_category

Emit = Callable[[str], None]


def expected_report_path(finance_root: str, month_key: str, report_dir: str) -> str:
    abbrev = month_key.partition("-")[0]
    month_number = list(calendar.month_abbr).index(abbrev.title())
    folder = calendar.month_name[month_number].lower()
    return str(
        PurePosixPath(finance_root)
        / "readable_documents"
        / "bank_statements"
        / folder
        / report_dir
        / "report.html"
    )


class ReportRepairWorkflow:
    def __init__(
        self,
        api: DashboardApi,
        navigator: ReportsNavigator,
        page,
        finance_root: str = "/home/adamsl/rol_finances",
        confidence_threshold: float = 0.90,
        emit: Emit = print,
    ) -> None:
        self.api = api
        self.navigator = navigator
        self.page = page
        self.finance_root = finance_root
        self.threshold = confidence_threshold
        self.emit = emit

    def _report_dir(self, target: RepairTarget) -> str:
        assert target.report is not None
        for month in self.navigator.month_tabs():
            for report in self.api.reports(month["key"]):
                if report.key == target.report.key and report.url:
                    return PurePosixPath(report.url).parent.name
        return target.report.key

    def _report_blocker(self, target: RepairTarget) -> Blocker:
        report = target.report
        assert report is not None
        if report.status == "missing":
            path = expected_report_path(
                self.finance_root, target.month_key, self._report_dir(target)
            )
            return Blocker(
                dialog="ok",
                tab=f"{target.month_label} → {target.tab_label}",
                problem="The tab is red because report.html is missing.",
                missing=(
                    "A source-anchored, audited report cannot be generated safely by "
                    "a generic repair rule. The correct statement PDF and account-specific "
                    "builder must be confirmed."
                ),
                instruction=(
                    f"Place the correct source statement PDF in {PurePosixPath(path).parent}/, "
                    "build and audit the report using "
                    "/home/adamsl/rol_finances/tools/python_tasks/verification_lib/"
                    f"REPORT_OUTPUT_CONTRACT.md, and save it as {path}. Click OK afterward; "
                    "the process will verify the file through the dashboard before continuing."
                ),
            )
        detail = report.attention_detail or report.failure_detail or {}
        summary = str(detail.get("summary") or detail.get("recommended_action") or "")
        return Blocker(
            dialog="yes_no",
            tab=f"{target.month_label} → {target.tab_label}",
            problem=f"The report is {report.status}. {summary}".strip(),
            missing=(
                "No deterministic repair matched with at least 90% identification and "
                "fix confidence. Source-versus-report review is required."
            ),
            instruction=(
                "Correct the report and run its source-consistency audit. Click YES to "
                "have the process recheck this same tab, or NO to stop without skipping it."
            ),
        )

    def _report_is_healthy(self, target: RepairTarget) -> bool:
        assert target.report is not None
        current = next(
            (r for r in self.api.reports(target.month_key) if r.key == target.report.key),
            None,
        )
        return current is not None and current.status == "pass" and current.exists

    def _handle_report(self, target: RepairTarget) -> bool:
        assert target.report is not None
        self.navigator.select_report(target.report.key)
        blocker = self._report_blocker(target)
        while True:
            self.emit(f"BLOCKED {blocker.tab}: {blocker.problem}")
            if not show_blocker(self.page, blocker):
                return False
            self.navigator.open()
            if self._report_is_healthy(target):
                self.emit(f"VERIFIED {blocker.tab}: pass")
                return True
            blocker = blocker.model_copy(
                update={
                    "problem": blocker.problem + " The requested correction is not visible yet."
                }
            )

    def _month_status(self, month_key: str) -> MonthStatus:
        return next(s for s in self.api.month_statuses() if s.month_key == month_key)

    def _handle_month(self, target: RepairTarget) -> bool:
        recent = self.api.recent_scans(target.month_key)
        status = self._month_status(target.month_key)
        target_id = int((status.most_recent_unfinished or {}).get("id") or 0)
        row = next((item for item in recent.rows if item.id == target_id), None)
        recommendation = (
            recommend_category(row, self.api.search_exact(row), self.threshold)
            if row is not None
            else None
        )
        if row is not None and recommendation is not None:
            self.emit(
                f"AUTO {target.tab_label}: expense {row.id} -> "
                f"{recommendation.category_name}; evidence={recommendation.evidence}"
            )
            result = self.api.recategorize(row, recommendation.category_name)
            failure = str(result.get("error") or "") if result.get("ok") is not True else ""
            if row.document_report and not result.get("matched_report"):
                failure = "The database changed, but the matching static report row did not."
            deadline = monotonic() + 15
            while not failure and monotonic() < deadline:
                saved = next(
                    (item for item in self.api.search_exact(row) if item.id == row.id),
                    None,
                )
                if (
                    saved is not None
                    and saved.category_name == recommendation.category_name
                    and self._month_status(target.month_key).status == "green"
                ):
                    self.emit(f"VERIFIED {target.tab_label}: status-green")
                    return True
                self.page.wait_for_timeout(300)
            evidence = (
                "The automatic repair did not verify: "
                f"{failure or 'the tab or stored category did not reach the expected state'}."
            )
        else:
            evidence = "No two unanimous exact-description and exact-amount precedents were found."

        if row is not None:
            evidence = f"Expense {row.id}: {row.description}, ${row.amount}. {evidence}"
        blocker = Blocker(
            dialog="yes_no",
            tab=target.tab_label,
            problem=f"The month tab is yellow because its newest expense is uncategorized. {evidence}",
            missing="A category decision with at least 90% confidence is unavailable.",
            instruction=(
                "Review and categorize the expense in New Records. Click YES to recheck the "
                "same tab, or NO to stop without changing or skipping it."
            ),
        )
        while True:
            if not show_blocker(self.page, blocker):
                return False
            self.navigator.open()
            if self._month_status(target.month_key).status == "green":
                self.emit(f"VERIFIED {target.tab_label}: status-green")
                return True
            blocker = blocker.model_copy(
                update={"problem": blocker.problem + " The tab is still yellow."}
            )

    def run(self, max_repairs: int = 100) -> int:
        self.navigator.open()
        for _ in range(max_repairs):
            target = self.navigator.next_unhealthy()
            if target is None:
                self.emit("ROL Finance Reports: no yellow or red tabs remain.")
                return 0
            self.emit(
                f"NEXT {target.month_label} -> {target.tab_label} ({target.kind})"
            )
            continued = (
                self._handle_report(target)
                if target.kind == "report"
                else self._handle_month(target)
            )
            if not continued:
                self.emit("Stopped without skipping the unresolved tab.")
                return 2
            self.navigator.open()
        raise RuntimeError(f"Stopped after {max_repairs} repairs to avoid an endless loop")
