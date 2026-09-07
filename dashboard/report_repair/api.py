"""Same-origin dashboard API adapter driven through Playwright."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote

from report_repair.models import (
    ExpenseRecord,
    MonthStatus,
    RecentScan,
    RecentScans,
    ReportState,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


class DashboardApi:
    def __init__(self, page: Page) -> None:
        self._page = page

    def _request(
        self, path: str, method: str = "GET", body: dict[str, Any] | None = None
    ) -> object:
        return cast(
            object,
            self._page.evaluate(
                """async ({path, method, body}) => {
                  const response = await fetch(path, {
                    method,
                    headers: body ? {'Content-Type': 'application/json'} : {},
                    body: body ? JSON.stringify(body) : undefined,
                  });
                  const text = await response.text();
                  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}: ${text}`);
                  try { return JSON.parse(text); }
                  catch { throw new Error(`${path}: response was not JSON`); }
                }""",
                {"path": path, "method": method, "body": body},
            ),
        )

    def reports(self, month_key: str) -> list[ReportState]:
        payload = self._request(
            f"/api/rol-finance-reports?month={quote(month_key, safe='')}"
        )
        if not isinstance(payload, list):
            raise RuntimeError("reports endpoint did not return a list")
        return [ReportState.model_validate(item) for item in payload]

    def month_statuses(self) -> list[MonthStatus]:
        payload = self._request("/api/rol-finance-month-status")
        if not isinstance(payload, dict) or not isinstance(payload.get("months"), list):
            raise RuntimeError("month-status endpoint returned an invalid payload")
        return [MonthStatus.model_validate(item) for item in payload["months"]]

    def recent_scans(self, month_key: str) -> RecentScans:
        payload = self._request(
            f"/api/rol-finance-recent-scans?limit=50&month={quote(month_key, safe='')}"
        )
        return RecentScans.model_validate(payload)

    def search_exact(self, row: RecentScan) -> list[ExpenseRecord]:
        payload = self._request(
            "/api/expense-search",
            "POST",
            {
                "merchant": row.description,
                "date_from": "",
                "date_to": "",
                "amount": float(row.amount),
                "limit": 50,
            },
        )
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            error = payload.get("error") if isinstance(payload, dict) else "invalid payload"
            raise RuntimeError(f"expense search failed: {error}")
        records = payload.get("records")
        if not isinstance(records, list):
            raise RuntimeError("expense search returned invalid records")
        return [ExpenseRecord.model_validate(item) for item in records]

    def recategorize(self, row: RecentScan, category_name: str) -> dict[str, Any]:
        payload = self._request(
            "/api/recategorize-expense",
            "POST",
            {
                "expense_id": row.id,
                "vendor_key": row.vendor_key,
                "description": row.description,
                "signed_amount": row.amount,
                "date": row.expense_date,
                "reporting_category": category_name,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("recategorize endpoint returned an invalid payload")
        return cast(dict[str, Any], payload)

