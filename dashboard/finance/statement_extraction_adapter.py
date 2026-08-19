"""Splitting one scanned page into transactions -- Mazda's own extraction step.

Named ``_adapter`` because rol_finances already owns a
``tools/receipt_scanning_tools/statement_extraction`` module; this is the
dashboard-side adapter that drives it through the preflight, not a second copy
of it.
"""

from __future__ import annotations

from finance.statement_credit_split import reviewable_flags
from finance.statement_models import (
    StatementBreakupRequest,
    StatementBreakupResponse,
    StatementRow,
)
from finance.statement_ports import IStatementExtractor, IStatementPreflightGateway


def _optional_float(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mark_reviewable(rows: list[StatementRow]) -> list[StatementRow]:
    """Flag each row using the WHOLE page's amounts -- a per-row read can't
    tell a mixed-sign page from an all-purchases one."""
    flags = reviewable_flags([(row.amount, row.description) for row in rows])
    return [row.model_copy(update={"reviewable": flag})
            for row, flag in zip(rows, flags)]


class PreflightStatementExtractor(IStatementExtractor):
    """Splits a scanned page using the automatic pipeline's own preflight.

    Driving run_statement_preflight rather than calling parse_statement_scan.py
    directly is the whole point: the preflight also resolves the bank and the
    account last-four (including the Known_Credit_Cards_and_Banks.xlsx lookup)
    and refuses a page holding two accounts. A hand-rolled second extraction
    would have to re-earn all of that, and would drift from what the automatic
    path stores for the same page.
    """

    def __init__(self, preflight: IStatementPreflightGateway) -> None:
        self._preflight = preflight

    def extract(self, request: StatementBreakupRequest) -> StatementBreakupResponse:
        metadata = {"bank_name": request.bank_name,
                    "account_last4": request.account_last4}
        result = self._preflight.run(request.image_path, metadata, request.engine)
        if result is None:
            return StatementBreakupResponse(
                ok=False,
                error="Statement preflight did not run for this document.")
        rows = [row for row in
                (StatementRow.from_parsed(raw)
                 for raw in self._preflight.rows(request.image_path, result))
                if row is not None]
        rows = _mark_reviewable(rows)
        return StatementBreakupResponse(
            ok=bool(result.get("ok")),
            bank_name=str(result.get("bank_name") or ""),
            account_last4=str(result.get("account_last4") or ""),
            last4_source=str(result.get("last4_source") or ""),
            statement_total=_optional_float(result.get("statement_total")),
            transactions=rows,
            needs_statement_metadata=bool(result.get("needs_statement_metadata")),
            missing_fields=[str(field) for field
                            in (result.get("missing_fields") or [])],
            error=(None if result.get("ok")
                   else str(result.get("error") or "statement extraction failed")),
        )
