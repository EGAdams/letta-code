"""Persist and present the human review state of an expense."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from pydantic import Field

from contracts import StrictModel


class HumanVerificationRequest(StrictModel):
    """The stable database identity sent when Set Category opens."""

    expense_id: int = Field(gt=0)


class HumanVerificationResult(StrictModel):
    ok: bool
    expense_id: int
    human_verified: bool
    error: str = ""


class IHumanVerificationRepository(ABC):
    @abstractmethod
    def mark_verified(self, expense_id: int) -> bool:
        """Set the flag and return whether the expense exists."""

    @abstractmethod
    def verified_ids(self, expense_ids: set[int]) -> set[int]:
        """Return the requested IDs whose flag is true."""


class MySqlHumanVerificationRepository(IHumanVerificationRepository):
    def __init__(self, connection_factory: Callable):
        self._connection_factory = connection_factory

    def mark_verified(self, expense_id: int) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, human_verified FROM expenses WHERE id=%s",
                    (expense_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return False
                if not bool(row.get("human_verified")):
                    cursor.execute(
                        "UPDATE expenses SET human_verified=1 WHERE id=%s",
                        (expense_id,),
                    )
        return True

    def verified_ids(self, expense_ids: set[int]) -> set[int]:
        if not expense_ids:
            return set()
        ordered = sorted(expense_ids)
        placeholders = ",".join(["%s"] * len(ordered))
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT id FROM expenses WHERE human_verified=1 "
                    f"AND id IN ({placeholders})",
                    tuple(ordered),
                )
                return {int(row["id"]) for row in cursor.fetchall()}


_VERIFIED_TABLE_RE = re.compile(
    r'<table\b[^>]*\bid="verified-transactions"[^>]*>.*?</table>',
    re.IGNORECASE | re.DOTALL,
)
_ROW_RE = re.compile(r"<tr\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_EXPENSE_ID_RE = re.compile(r'\bdata-expense-id="(?P<id>\d+)"', re.IGNORECASE)
_CLASS_RE = re.compile(r'\bclass="(?P<classes>[^"]*)"', re.IGNORECASE)
_HUMAN_ATTR_RE = re.compile(r'\s+data-human-verified="[^"]*"', re.IGNORECASE)


def _verification_attrs(attrs: str, verified: bool) -> str:
    attrs = _HUMAN_ATTR_RE.sub("", attrs)
    class_match = _CLASS_RE.search(attrs)
    classes = class_match.group("classes").split() if class_match else []
    classes = [name for name in classes if name != "human-verified"]
    if verified:
        classes.append("human-verified")
    if class_match:
        replacement = f'class="{" ".join(classes)}"'
        attrs = attrs[:class_match.start()] + replacement + attrs[class_match.end():]
    elif classes:
        attrs += f' class="{" ".join(classes)}"'
    if verified:
        attrs += ' data-human-verified="true"'
    return attrs


def decorate_verified_rows(report_html: str, verified_ids: Iterable[int]) -> str:
    """Apply database-authoritative markers to the Verified Transactions table."""
    verified = {int(expense_id) for expense_id in verified_ids}
    table_match = _VERIFIED_TABLE_RE.search(report_html)
    if table_match is None:
        return report_html

    def replace_row(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        id_match = _EXPENSE_ID_RE.search(attrs)
        if id_match is None:
            return match.group(0)
        expense_id = int(id_match.group("id"))
        return f"<tr{_verification_attrs(attrs, expense_id in verified)}>"

    table = _ROW_RE.sub(replace_row, table_match.group(0))
    return report_html[:table_match.start()] + table + report_html[table_match.end():]


class HumanVerificationService:
    def __init__(self, repository: IHumanVerificationRepository):
        self._repository = repository

    def mark_verified(self, request: HumanVerificationRequest) -> HumanVerificationResult:
        found = self._repository.mark_verified(request.expense_id)
        if not found:
            return HumanVerificationResult(
                ok=False,
                expense_id=request.expense_id,
                human_verified=False,
                error=f"Expense {request.expense_id} was not found.",
            )
        return HumanVerificationResult(
            ok=True,
            expense_id=request.expense_id,
            human_verified=True,
        )

    def decorate_report(self, report_html: str) -> str:
        table_match = _VERIFIED_TABLE_RE.search(report_html)
        if table_match is None:
            return report_html
        expense_ids = {
            int(match.group("id"))
            for match in _EXPENSE_ID_RE.finditer(table_match.group(0))
        }
        return decorate_verified_rows(
            report_html,
            self._repository.verified_ids(expense_ids),
        )
