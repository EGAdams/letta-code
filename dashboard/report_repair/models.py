"""Typed data crossing the ROL Finance repair browser boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MonthStatus(BoundaryModel):
    month_key: str
    status: str
    uncategorized_count: int = 0
    most_recent_unfinished: dict[str, Any] | None = None


class RecentScan(BoundaryModel):
    id: int
    vendor_key: str = ""
    description: str
    expense_date: str
    amount: str
    reporting_category: str = "Uncategorized"
    reason: str = ""
    document_report: dict[str, Any] | None = None


class RecentScans(BoundaryModel):
    rows: list[RecentScan] = Field(default_factory=list)
    queue_total: int = 0
    month_key: str


class ExpenseRecord(BoundaryModel):
    id: int
    transaction_date: str
    total_amount: float
    description: str
    id_light: str = ""
    category_name: str = ""


class ReportState(BoundaryModel):
    key: str
    label: str
    exists: bool
    status: str | None = None
    url: str | None = None
    attention_detail: dict[str, Any] | None = None
    failure_detail: dict[str, Any] | None = None


class RepairTarget(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["month", "report"]
    month_key: str
    month_label: str
    tab_label: str
    report: ReportState | None = None


class CategoryRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)
    category_name: str
    identification_confidence: float
    fix_confidence: float
    evidence: list[str]


class Blocker(BaseModel):
    model_config = ConfigDict(frozen=True)
    dialog: Literal["ok", "yes_no"]
    tab: str
    problem: str
    missing: str
    instruction: str

