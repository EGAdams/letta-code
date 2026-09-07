from report_repair.models import ExpenseRecord, RecentScan
from report_repair.policy import recommend_category
from report_repair.workflow import expected_report_path


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
        "/home/adamsl/rol_finances", "mar-2025", "december_january_personal_bank_statement"
    ) == (
        "/home/adamsl/rol_finances/readable_documents/bank_statements/march/"
        "december_january_personal_bank_statement/report.html"
    )
