"""Pure argv/payload builders for the two statement scripts. No I/O.

These are the STATEMENT BRANCH commands Mazda is told to run verbatim (see
server.py's build_mazda_scan_message), plus the handwriting pass
statement_review.resolve_review already runs after a successful store. Kept
pure and separate so a test can assert on the exact argv without a subprocess.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from statement_review import ANNOTATION_SCRIPT, RF_VENV_PY, STORE_SCRIPT

from finance.statement_models import StatementStoreRequest

__all__ = [
    "ANNOTATION_SCRIPT",
    "RF_VENV_PY",
    "STORE_SCRIPT",
    "build_annotation_command",
    "build_store_command",
    "build_store_payload",
]


def build_store_payload(request: StatementStoreRequest) -> dict[str, Any]:
    """The corrected rows in parse_statement_scan.py's own envelope.

    Handing the store the parser's shape -- rather than one invented here -- is
    what makes "the operator fixed row 3" indistinguishable, downstream, from
    "the parser read row 3 correctly". FlexibleStatementNormalizer accepts this
    envelope directly.
    """
    return {
        "ok": True,
        "doc_kind": "statement",
        "source_image": request.image_path,
        "statement_count": 1,
        "statements": [{
            "bank_name": request.bank_name,
            "account_number": request.account_last4,
            "statement_total": request.statement_total,
            "transaction_count": len(request.transactions),
            "transactions": [
                {"date": row.transaction_date,
                 "description": row.description,
                 "amount": row.amount}
                for row in request.transactions
            ],
        }],
    }


def build_store_command(request: StatementStoreRequest,
                        payload_path: str) -> list[str]:
    """The STATEMENT BRANCH's S2 command.

    The free-text values use ``--opt=value``: argparse reads a separate value
    beginning with a dash as an unknown option, so a bank name like
    "-Wells Fargo" would fail the RUN rather than the field. Same fix, same
    reason, as manual_entry.build_save_command's merchant override.
    """
    command = [
        RF_VENV_PY, STORE_SCRIPT,
        "-f", payload_path,
        f"--source-file={request.image_path}",
        f"--bank-name={request.bank_name}",
        f"--account-last4={request.account_last4}",
    ]
    if request.last4_source:
        command += ["--account-last4-source", request.last4_source]
    return command


def build_annotation_command(image_path: str,
                             expense_ids: Sequence[int]) -> list[str]:
    """The handwritten-category pass, over every row the store touched."""
    return [
        RF_VENV_PY, ANNOTATION_SCRIPT,
        f"--image={image_path}",
        "--expense-ids", ",".join(str(expense_id) for expense_id in expense_ids),
    ]
