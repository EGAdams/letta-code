"""Coercing untrusted JSON scalars, once, with booleans kept out.

The strict Pydantic models these feed deliberately refuse a number that
arrives as a string, so every HTTP handler coerces at the boundary first.
That coercion was written inline, once per handler, as::

    try:
        total_amount = float(data.get('total_amount'))
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'total_amount must be a number'}

Repeated four times, and all four shared a hole: ``bool`` is a subclass of
``int`` in Python, so ``int(True)`` is 1 and ``float(True)`` is 1.0 -- both
succeed silently. A request sending ``{"expense_id": true}`` was therefore
accepted and went on to edit expense row 1 (confirmed against the live
endpoint, which got as far as "no expense with id 1"). JSON's ``true`` is not
a number and must be refused as one.

Raises ValueError with a message written for the operator, which the handlers
turn into an ``{'ok': False, 'error': ...}`` response.
"""

from __future__ import annotations

from typing import Any, Optional


def _reject_bool(value: Any, field: str) -> None:
    # Checked before the int()/float() call, never after: by then True has
    # already become 1 and the information that it was a boolean is gone.
    if isinstance(value, bool):
        raise ValueError(f'{field} must be a number, not a boolean')


def as_int(value: Any, field: str) -> int:
    """JSON scalar -> int, or ValueError naming the field."""
    _reject_bool(value, field)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be an integer') from None


def as_float(value: Any, field: str) -> float:
    """JSON scalar -> float, or ValueError naming the field."""
    _reject_bool(value, field)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} must be a number') from None


def as_optional_float(value: Any, field: str) -> Optional[float]:
    """Like as_float, but treats absent/blank as "not supplied"."""
    if value is None or value == '':
        return None
    return as_float(value, field)


def as_optional_int(value: Any, field: str) -> Optional[int]:
    """Like as_int, but treats absent/blank as "not supplied"."""
    if value is None or value == '':
        return None
    return as_int(value, field)
