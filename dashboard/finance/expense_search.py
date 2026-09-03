"""Pure request, SQL-clause, and validation helpers for expense search."""
from __future__ import annotations

from typing import Any, Optional

from finance.expense_edit_model import AMOUNT_MATCH_TOLERANCE, ExpenseSearchCriteria
from finance.http_coercion import as_optional_float, as_optional_int


LIKE_ESCAPE = '!'


def escape_like(text: str) -> str:
    """Escape SQL LIKE metacharacters after values have been parameterized."""
    out = text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    return out.replace('%', f'{LIKE_ESCAPE}%').replace('_', f'{LIKE_ESCAPE}_')


def where_clauses(criteria: ExpenseSearchCriteria,
                  has_vendor_key: bool) -> tuple[list[str], list[Any]]:
    """Criteria -> parameterized SQL fragments and their bind values."""
    clauses: list[str] = []
    params: list[Any] = []
    if criteria.merchant:
        like = f'%{escape_like(criteria.merchant)}%'
        escape = f" ESCAPE '{LIKE_ESCAPE}'"
        if has_vendor_key:
            clauses.append(
                f'(description LIKE %s{escape} OR id_light LIKE %s{escape})')
            params += [like, like]
        else:
            clauses.append(f'description LIKE %s{escape}')
            params.append(like)
    if criteria.date_from:
        clauses.append('expense_date >= %s')
        params.append(criteria.date_from)
    if criteria.date_to:
        clauses.append('expense_date <= %s')
        params.append(criteria.date_to)
    if criteria.amount is not None:
        clauses.append('ABS(ABS(amount) - %s) < %s')
        params += [criteria.amount, AMOUNT_MATCH_TOLERANCE]
    return clauses, params


def search_criteria_from_request(data: dict) -> ExpenseSearchCriteria:
    """Coerce an untrusted HTTP JSON shape into the strict search model."""
    data = data or {}
    amount = as_optional_float(data.get('amount'), 'amount')
    limit = as_optional_int(data.get('limit') or None, 'limit')
    fields: dict[str, Any] = {
        'merchant': str(data.get('merchant') or ''),
        'date_from': _optional_text(data.get('date_from')),
        'date_to': _optional_text(data.get('date_to')),
        'amount': amount,
    }
    if limit is not None:
        fields['limit'] = limit
    return ExpenseSearchCriteria(**fields)


def _optional_text(value: Any) -> Optional[str]:
    text = str(value or '').strip()
    return text or None


def readable_validation_error(exc: Exception) -> str:
    """Render a Pydantic error as one sentence an operator can act on."""
    errors = getattr(exc, 'errors', None)
    if not callable(errors):
        return str(exc)
    messages = []
    for error in errors():
        message = str(error.get('msg') or '').strip()
        message = message.removeprefix('Value error, ')
        location = '.'.join(str(part) for part in error.get('loc') or ())
        if message:
            messages.append(f'{location}: {message}' if location else message)
    return '; '.join(messages) or str(exc)
