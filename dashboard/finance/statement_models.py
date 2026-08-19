"""Strict boundary models for one scanned statement broken into many expenses.

A receipt carries one expense, so the manual-entry form's single
merchant/date/amount triple is enough for it. A *statement* page carries
several -- the 2026-08-19 Last Window Scan held five -- and every fill button
asks the receipt parser, which answers with one. These are the shapes the
statement path speaks instead.

Models only: no ABCs, no subprocesses, no transport. See statement_ports.py for
the interfaces and statement_store.py / statement_extraction.py for the
adapters that satisfy them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finance.http_coercion import as_float, as_optional_float


class StrictBoundaryModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class StatementRow(StrictBoundaryModel):
    """One transaction line -- one stop on the form's Prev/Next walk.

    ``amount`` is deliberately unconstrained in sign. Statements print purchases
    and credits with opposite conventions, and deciding which is which is
    ``store_statement_transactions.py``'s job (its ``split_expenses_and_credits``
    reads the whole page's sign pattern, then falls back to a payment/credit
    description pattern). Rejecting a negative row here would mean refusing to
    show the operator a line the store will simply and correctly skip -- and a
    local second opinion about the sign is exactly what drifts away from the
    tool that decides.
    """

    transaction_date: str
    description: str
    amount: float
    unreadable: bool = False
    # Set by the extractor (statement_credit_split.reviewable_flags), never by
    # the operator or a caller: whether this row belongs on the Prev/Next
    # review list, or is an obvious payment/credit/zero-amount line the store
    # was always going to skip. Purely a display hint -- Save All still submits
    # every row, reviewable or not, so the store's own split (over the complete
    # page) remains the one place that decision is actually made.
    reviewable: bool = True

    @field_validator("transaction_date")
    @classmethod
    def _date_is_iso(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("description")
    @classmethod
    def _description_non_empty(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("description is required")
        return cleaned

    @classmethod
    def from_parsed(cls, row: Mapping[str, Any]) -> "StatementRow | None":
        """One parse_statement_scan.py row -> a display row, or None.

        The parser's key is ``date``; a row it could not fully read stays in its
        output rather than being dropped, so a row that cannot satisfy the model
        is skipped here instead of failing the whole extraction. The operator
        gets the rows that were read and adds the rest by hand, which beats an
        all-or-nothing refusal on a page that was 90% legible.
        """
        if not isinstance(row, Mapping):
            return None
        try:
            return cls(
                transaction_date=str(row.get("date") or ""),
                description=str(row.get("description") or ""),
                amount=as_float(row.get("amount"), "amount"),
                unreadable=bool(row.get("unreadable")),
            )
        except (ValueError, TypeError):
            return None


#: The three engine values rol_finances' parse_statement_scan.py's own
#: --engine flag accepts (tools/receipt_scanning_tools/parse_statement_scan.py
#: STATEMENT_PREVIEW_ENGINES). Kept in sync deliberately: this value crosses
#: the process boundary as a literal CLI argument, so a name added on one side
#: without the other would surface as a cryptic argparse failure instead of a
#: clear 400 here.
STATEMENT_ENGINES = frozenset({"auto", "gemini-only", "haiku-only"})


class StatementBreakupRequest(StrictBoundaryModel):
    """"Break Up Document" -- read every transaction off one scanned page."""

    image_path: str
    bank_name: str = ""
    account_last4: str = ""
    #: "auto" (the full Gemini/Codex/ChatGPT/OpenAI fallback chain) is a valid
    #: value but never offered by the dashboard's own two buttons -- an
    #: operator who already chose "Read with Gemini" or "Read with Haiku" gets
    #: exactly that provider, with no silent fallback to a different one.
    engine: str = "auto"

    @field_validator("image_path")
    @classmethod
    def _image_path_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("image_path is required")
        return value

    @field_validator("engine")
    @classmethod
    def _known_engine(cls, value: str) -> str:
        if value not in STATEMENT_ENGINES:
            raise ValueError(f"engine must be one of {sorted(STATEMENT_ENGINES)}")
        return value

    @classmethod
    def from_http(cls, data: Mapping[str, Any] | None) -> "StatementBreakupRequest":
        data = data or {}
        return cls(
            image_path=str(data.get("image_path") or "").strip(),
            bank_name=" ".join(str(data.get("bank_name") or "").split()),
            account_last4=str(data.get("account_last4") or "").strip(),
            engine=str(data.get("engine") or "auto").strip(),
        )


class StatementBreakupResponse(StrictBoundaryModel):
    """What the form needs to fill its item list and its statement header.

    ``transactions`` is populated even when ``ok`` is False for a
    ``needs_statement_metadata`` result: the rows were read and only the account
    identity is missing, so the operator should see the five expenses while
    typing the bank in -- not an empty form behind an error.
    """

    ok: bool
    bank_name: str = ""
    account_last4: str = ""
    last4_source: str = ""
    statement_total: float | None = None
    transactions: list[StatementRow] = Field(default_factory=list)
    needs_statement_metadata: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    error: str | None = None

    def to_http(self) -> dict[str, Any]:
        return self.model_dump()


class StatementStoreRequest(StrictBoundaryModel):
    """Save All, in statement mode: every corrected row, stored in one pass.

    One request holds the whole page because ``store_statement_transactions.py``
    duplicate-checks and archives a statement as a unit. Posting rows one at a
    time would run the account verification and the archive move five times for
    one page, and would report five unrelated outcomes instead of the single
    "5 read, 1 credit skipped, 2 duplicates, 2 stored" the tool already produces.
    """

    image_path: str
    bank_name: str
    account_last4: str
    statement_total: float | None = None
    last4_source: str = ""
    conversation_id: str = ""
    transactions: list[StatementRow] = Field(min_length=1)

    @field_validator("image_path", "bank_name", "account_last4")
    @classmethod
    def _required_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value is required")
        return value

    @field_validator("last4_source")
    @classmethod
    def _known_last4_source(cls, value: str) -> str:
        # store_statement_transactions.py's --account-last4-source is a
        # choices=() argument: an unrecognized value is an argparse error, not a
        # store failure, so it never reaches the report the operator reads.
        if value and value not in ("operator", "known_cards_workbook"):
            raise ValueError(
                "last4_source must be 'operator' or 'known_cards_workbook'")
        return value

    @classmethod
    def from_http(cls, data: Mapping[str, Any] | None) -> "StatementStoreRequest":
        """Coerce the untrusted JSON shape once, before the strict model.

        Same boundary discipline as submit_manual_receipt_entry: the model
        refuses a number that arrived as a string on purpose, so the strings a
        browser's <input> always sends are converted here, in one place, with
        the offending field named in any error the operator sees.
        """
        data = data or {}
        rows = data.get("transactions")
        if not isinstance(rows, list):
            raise ValueError("transactions must be a list")
        transactions = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise ValueError(f"transaction {index} must be an object")
            transactions.append(StatementRow(
                transaction_date=str(row.get("transaction_date") or ""),
                description=" ".join(str(row.get("description") or "").split()),
                amount=as_float(row.get("amount"), f"transaction {index} amount"),
                unreadable=bool(row.get("unreadable")),
            ))
        return cls(
            image_path=str(data.get("image_path") or "").strip(),
            bank_name=" ".join(str(data.get("bank_name") or "").split()),
            account_last4=str(data.get("account_last4") or "").strip(),
            statement_total=as_optional_float(
                data.get("statement_total"), "statement_total"),
            last4_source=str(data.get("last4_source") or "").strip(),
            conversation_id=str(data.get("conversation_id") or "").strip(),
            transactions=transactions,
        )


class StatementStoreResponse(StrictBoundaryModel):
    """store_statement_transactions.py's own report, typed.

    The counts are the store's, not this module's: "stored" already excludes the
    credits it skipped and the duplicates it recognized, which is precisely what
    a human hand-entering five statement lines cannot work out for themselves.
    """

    ok: bool
    transactions_parsed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped_credits: int = 0
    uncategorized: int = 0
    failed: int = 0
    expense_ids: list[int] = Field(default_factory=list)
    duplicate_expense_ids: list[int] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    error: str | None = None

    def to_http(self) -> dict[str, Any]:
        return self.model_dump()

    @property
    def annotatable_expense_ids(self) -> list[int]:
        """Every row the handwriting pass should look at, each ID once.

        Duplicates are included deliberately: an already-stored expense still
        gains the marked-up scan as evidence, which is what
        statement_review.resolve_review does with the same two lists.
        """
        seen: list[int] = []
        for expense_id in list(self.expense_ids) + list(self.duplicate_expense_ids):
            if expense_id not in seen:
                seen.append(expense_id)
        return seen


class CommandResult(StrictBoundaryModel):
    """One finished subprocess, as the existing script runners describe one."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    returncode: int = 1
    stdout: str = ""
    stderr: str = ""
    report: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_runner(cls, result: Mapping[str, Any] | None) -> "CommandResult":
        result = result or {}
        report = result.get("report")
        return cls(
            returncode=int(result.get("returncode") or 0),
            stdout=str(result.get("stdout") or ""),
            stderr=str(result.get("stderr") or ""),
            report=dict(report) if isinstance(report, Mapping) else {},
        )

    @property
    def failure_text(self) -> str:
        return (str(self.report.get("error") or "")
                or self.stderr.strip() or self.stdout.strip() or "command failed")
