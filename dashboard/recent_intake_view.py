from __future__ import annotations

"""Helpers for the synthetic recent-intake / scanner-report view.

These helpers are intentionally small and pure so recent-intake rendering can
move out of server.py slice by slice without dragging DB or HTTP machinery
along with it.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable


_CHECK_RE = re.compile(r"^\s*check\b", re.IGNORECASE)
_DOCUMENT_FIELDS = (
    "receipt_url",
    "document_url",
    "scanned_statement_url",
    "moms_ledger",
)


def is_check_like_description(text: str | None) -> bool:
    return bool(_CHECK_RE.match(str(text or "").strip()))


def _amount_key(value) -> str:
    try:
        return str(abs(Decimal(str(value))))
    except (InvalidOperation, TypeError, ValueError):
        return str(value or "")


def _group_key(row: dict) -> tuple[str, str]:
    return str(row.get("date") or ""), _amount_key(row.get("amount"))


def _preference_key(row: dict) -> tuple[int, int, int, int, int]:
    has_receipt = 1 if str(row.get("receipt_url") or "").strip() else 0
    has_source = 1 if str(row.get("document_url") or "").strip() else 0
    has_other_evidence = 1 if (
        str(row.get("scanned_statement_url") or "").strip()
        or str(row.get("moms_ledger") or "").strip()
    ) else 0
    non_check = 0 if is_check_like_description(row.get("description")) else 1
    description_len = len(str(row.get("description") or "").strip())
    return (non_check, has_receipt, has_source, has_other_evidence, description_len)


def merge_supporting_document_fields(primary: dict, siblings: Iterable[dict]) -> dict:
    merged = dict(primary)
    for sibling in siblings:
        for field in _DOCUMENT_FIELDS:
            if str(merged.get(field) or "").strip():
                continue
            value = str((sibling or {}).get(field) or "").strip()
            if value:
                merged[field] = value
    return merged


def collapse_check_evidence_rows(rows: Iterable[dict], duplicate_ids=()):
    """Collapse one real-world expense plus its check-evidence sibling rows.

    When a same-date/same-amount group contains both a check-like row
    ("Check 11049") and a non-check expense row ("Tikun International"), the
    dashboard should render one visible expense row and merge the supporting
    document slots across the sibling rows.
    """
    rows = list(rows or [])
    duplicate_ids = {int(i) for i in (duplicate_ids or []) if str(i).isdigit()}
    grouped = defaultdict(list)
    for row in rows:
        grouped[_group_key(row)].append(row)

    collapsed = []
    promoted_duplicates = set()
    for group in grouped.values():
        has_check = any(is_check_like_description(r.get("description")) for r in group)
        has_non_check = any(not is_check_like_description(r.get("description")) for r in group)
        if len(group) > 1 and has_check and has_non_check:
            primary = max(group, key=_preference_key)
            merged = merge_supporting_document_fields(primary, group)
            collapsed.append(merged)
            group_ids = {
                int(r["id"]) for r in group
                if str((r or {}).get("id") or "").isdigit()
            }
            if duplicate_ids.intersection(group_ids) and str(merged.get("id") or "").isdigit():
                promoted_duplicates.add(int(merged["id"]))
            continue
        collapsed.extend(group)
        for row in group:
            if str((row or {}).get("id") or "").isdigit() and int(row["id"]) in duplicate_ids:
                promoted_duplicates.add(int(row["id"]))
    return collapsed, promoted_duplicates