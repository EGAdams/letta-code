"""Evidence threshold for automatic expense categorization."""

from __future__ import annotations

from decimal import Decimal

from report_repair.models import (
    CategoryRecommendation,
    ExpenseRecord,
    RecentScan,
)


def _words(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _cents(value: str | float) -> Decimal:
    return Decimal(str(value)).copy_abs().quantize(Decimal("0.01"))


def recommend_category(
    target: RecentScan,
    records: list[ExpenseRecord],
    threshold: float = 0.90,
) -> CategoryRecommendation | None:
    """Recommend only from two unanimous, exact-description/amount precedents."""
    matches = [
        row
        for row in records
        if row.id != target.id
        and _words(row.description) == _words(target.description)
        and _cents(row.total_amount) == _cents(target.amount)
        and row.category_name
        and row.category_name.casefold() != "uncategorized"
    ]
    categories = {row.category_name for row in matches}
    if len(matches) < 2 or len(categories) != 1:
        return None
    category = next(iter(categories))
    identification_confidence = 0.99
    fix_confidence = 0.98
    if min(identification_confidence, fix_confidence) < threshold:
        return None
    evidence = [
        f"expense {row.id}: {row.transaction_date}, "
        f"${row.total_amount:.2f}, {row.category_name}"
        for row in matches
    ]
    return CategoryRecommendation(
        category_name=category,
        identification_confidence=identification_confidence,
        fix_confidence=fix_confidence,
        evidence=evidence,
    )

