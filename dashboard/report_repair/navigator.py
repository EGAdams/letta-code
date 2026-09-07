"""Playwright navigation and unhealthy-tab discovery in visual order."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from report_repair.api import DashboardApi
from report_repair.models import RepairTarget

if TYPE_CHECKING:
    from playwright.sync_api import Page


class ReportsNavigator:
    def __init__(self, page: Page, dashboard_url: str, api: DashboardApi) -> None:
        self._page = page
        self._url = dashboard_url.rstrip("/")
        self._api = api

    def open(self) -> None:
        self._page.goto(
            f"{self._url}/?view=rol-finance-reports",
            wait_until="commit",
            timeout=60_000,
        )
        self._page.wait_for_function(
            "document.querySelectorAll('#nav-rol-finance-reports .month-tab').length > 0",
            timeout=30_000,
        )
        self._page.wait_for_function(
            "[...document.querySelectorAll('#nav-rol-finance-reports .month-tab')]"
            ".every(x => x.classList.contains('status-green') || "
            "x.classList.contains('status-yellow') || x.classList.contains('status-red'))",
            timeout=30_000,
        )

    def month_tabs(self) -> list[dict[str, str]]:
        return cast(
            list[dict[str, str]],
            self._page.evaluate(
                """[...document.querySelectorAll('#nav-rol-finance-reports .month-tab')]
                  .map(x => ({key:x.dataset.monthKey, label:x.textContent.trim(), cls:x.className}))"""
            ),
        )

    def open_month(self, month_key: str, month_label: str, report_count: int) -> None:
        self._page.evaluate(
            """key => {
              const tab = [...document.querySelectorAll('#nav-rol-finance-reports .month-tab')]
                .find(x => x.dataset.monthKey === key);
              if (!tab) throw new Error(`month tab ${key} is missing`);
              tab.click();
            }""",
            month_key,
        )
        self._page.wait_for_function(
            "({count, heading}) => { const h=document.querySelector("
            "'#rol-finance-reports-overview h2'); return h && "
            "h.textContent.trim() === heading && document.querySelectorAll("
            "'#nav-rol-finance-reports .tab[data-report-key]').length === count; }",
            arg={
                "count": report_count,
                "heading": f"{month_label} — Document Status",
            },
            timeout=30_000,
        )

    def next_unhealthy(self) -> RepairTarget | None:
        statuses = {item.month_key: item for item in self._api.month_statuses()}
        for month in self.month_tabs():
            reports = self._api.reports(month["key"])
            self.open_month(month["key"], month["label"], len(reports))
            for report in reports:
                if report.status not in {"missing", "review", "fail"}:
                    continue
                tab_class = self._page.locator(
                    f'#nav-rol-finance-reports .tab[data-report-key="{report.key}"]'
                ).get_attribute("class") or ""
                if "status-yellow" not in tab_class and "report-missing" not in tab_class:
                    raise RuntimeError(
                        f"API says {report.label} is {report.status}, but its tab is {tab_class!r}"
                    )
                return RepairTarget(
                    kind="report",
                    month_key=month["key"],
                    month_label=month["label"].title(),
                    tab_label=report.label,
                    report=report,
                )
            status = statuses.get(month["key"])
            if status and status.status in {"yellow", "red"}:
                return RepairTarget(
                    kind="month",
                    month_key=month["key"],
                    month_label=month["label"].title(),
                    tab_label=month["label"].title(),
                )
        return None

    def select_report(self, report_key: str) -> None:
        self._page.locator(
            f'#nav-rol-finance-reports .tab[data-report-key="{report_key}"]'
        ).click()
