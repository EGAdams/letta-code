from unittest.mock import MagicMock

from report_repair.models import ExpenseRecord, MonthStatus, RecentScan, ReportState
from report_repair.navigator import ReportsNavigator
from report_repair.policy import recommend_category
from report_repair.workflow import ReportRepairWorkflow, expected_report_path


def scan() -> RecentScan:
    return RecentScan(
        id=2669,
        vendor_key="commercial_loan",
        description="5/3 COMMRCL LN #0026 PAID BY AUTO BILLPAYER",
        expense_date="2025-02-28",
        amount="2518.46",
    )


def record(expense_id: int, category: str, amount: float = 2518.46) -> ExpenseRecord:
    return ExpenseRecord(
        id=expense_id,
        transaction_date="2025-01-31",
        total_amount=amount,
        description="5/3 COMMRCL LN #0026 PAID BY AUTO BILLPAYER",
        category_name=category,
    )


def test_two_unanimous_exact_precedents_clear_the_ninety_percent_threshold():
    result = recommend_category(
        scan(), [record(1180, "Church Facility Payments"), record(2681, "Church Facility Payments")]
    )

    assert result is not None
    assert result.category_name == "Church Facility Payments"
    assert result.identification_confidence >= 0.90
    assert result.fix_confidence >= 0.90


def test_one_precedent_or_conflicting_precedents_require_a_human():
    assert recommend_category(scan(), [record(1180, "Church Facility Payments")]) is None
    assert recommend_category(
        scan(), [record(1180, "Church Facility Payments"), record(2681, "Money Movement")]
    ) is None


def test_amount_or_description_drift_is_not_treated_as_exact_evidence():
    different = record(2681, "Church Facility Payments", amount=2518.45)
    assert recommend_category(scan(), [record(1180, "Church Facility Payments"), different]) is None


def test_missing_report_dialog_gets_the_exact_destination_path():
    assert expected_report_path(
        "/home/adamsl/rol_finances", "mar-2025", "bank_5938_pdf1"
    ) == (
        "/home/adamsl/rol_finances/readable_documents/bank_statements/march/"
        "bank_5938_pdf1/report.html"
    )


# ── ReportRepairWorkflow.run: skip-yellow-months ──────────────────────────

def month_target(month_key: str):
    from report_repair.models import RepairTarget
    return RepairTarget(
        kind="month", month_key=month_key,
        month_label=month_key.title(), tab_label=month_key.title(),
    )


def report_target(month_key: str, report_key: str, status: str = "missing"):
    from report_repair.models import RepairTarget
    return RepairTarget(
        kind="report", month_key=month_key,
        month_label=month_key.title(), tab_label=report_key,
        report=ReportState(key=report_key, label=report_key, exists=False, status=status),
    )


def make_workflow(**kwargs) -> tuple[ReportRepairWorkflow, MagicMock]:
    api = MagicMock()
    navigator = MagicMock()
    page = MagicMock()
    workflow = ReportRepairWorkflow(api, navigator, page, **kwargs)
    return workflow, navigator


def test_skip_yellow_months_passes_over_a_yellow_month_without_blocking():
    workflow, navigator = make_workflow(skip_yellow_months=True)
    navigator.next_unhealthy.side_effect = [month_target("mar-2025"), None]

    result = workflow.run()

    assert result == 0
    # Never touched the blocker/handle-month path for the skipped yellow month.
    workflow_calls = [c.args for c in navigator.next_unhealthy.call_args_list]
    assert workflow_calls == [(frozenset(),), (frozenset({"mar-2025"}),)]


def test_skip_yellow_months_still_repairs_a_later_red_report():
    workflow, navigator = make_workflow(skip_yellow_months=True)
    target = report_target("apr-2025", "bank-5938-pdf1")
    navigator.next_unhealthy.side_effect = [month_target("mar-2025"), target, None]
    workflow._handle_report = MagicMock(return_value=True)

    result = workflow.run()

    assert result == 0
    workflow._handle_report.assert_called_once_with(target)


def test_without_skip_yellow_months_a_yellow_month_still_blocks():
    workflow, navigator = make_workflow(skip_yellow_months=False)
    target = month_target("mar-2025")
    navigator.next_unhealthy.side_effect = [target]
    workflow._handle_month = MagicMock(return_value=False)

    result = workflow.run()

    assert result == 2
    workflow._handle_month.assert_called_once_with(target)


def test_navigator_next_unhealthy_skips_a_yellow_month_to_find_a_later_red_report():
    page = MagicMock()
    api = MagicMock()
    api.month_statuses.return_value = [
        MonthStatus(month_key="mar-2025", status="yellow"),
        MonthStatus(month_key="apr-2025", status="red"),
    ]
    api.reports.side_effect = lambda key: {
        "mar-2025": [ReportState(key="ok-report", label="OK Report", exists=True, status="pass")],
        "apr-2025": [ReportState(key="bank-5938-pdf1", label="Bank 5938 PDF 1",
                                  exists=False, status="missing")],
    }[key]

    navigator = ReportsNavigator(page, "http://x", api)
    navigator.month_tabs = MagicMock(return_value=[
        {"key": "mar-2025", "label": "March 2025", "cls": ""},
        {"key": "apr-2025", "label": "April 2025", "cls": ""},
    ])
    navigator.open_month = MagicMock()
    locator = MagicMock()
    locator.get_attribute.return_value = "tab report-missing"
    page.locator.return_value = locator

    without_skip = navigator.next_unhealthy()
    assert without_skip is not None
    assert without_skip.kind == "month"
    assert without_skip.month_key == "mar-2025"

    with_skip = navigator.next_unhealthy(frozenset({"mar-2025"}))
    assert with_skip is not None
    assert with_skip.kind == "report"
    assert with_skip.month_key == "apr-2025"
    assert with_skip.report.key == "bank-5938-pdf1"
