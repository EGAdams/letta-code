from __future__ import annotations

"""Helpers for supporting-document resolution."""

from collections.abc import Mapping
import os
from urllib.parse import unquote, urlparse


def normalize_supporting_document_reference(reference) -> str:
    if isinstance(reference, Mapping):
        candidate = (
            reference.get("receipt_id")
            or reference.get("source_document_id")
            or reference.get("source_document")
            or reference.get("id")
            or reference.get("document_id")
        )
        return normalize_supporting_document_reference(candidate)
    text = str(reference or "").strip()
    if text.startswith("receipt:") and not text.startswith("receipt://"):
        return text[len("receipt:"):].strip()
    return text


def references_same_underlying_document(
    left,
    right,
    *,
    resolve_local_path,
) -> bool:
    left_ref = normalize_supporting_document_reference(left)
    right_ref = normalize_supporting_document_reference(right)
    if not left_ref or not right_ref:
        return False
    if left_ref == right_ref:
        return True

    left_url = _normalized_url_identity(left_ref)
    right_url = _normalized_url_identity(right_ref)
    if left_url and right_url:
        return left_url == right_url

    left_path = _normalized_local_identity(left_ref, resolve_local_path)
    right_path = _normalized_local_identity(right_ref, resolve_local_path)
    return bool(left_path and right_path and left_path == right_path)


def should_suppress_source_document(
    source_reference,
    receipt_reference,
    *,
    resolve_local_path,
) -> bool:
    return references_same_underlying_document(
        source_reference,
        receipt_reference,
        resolve_local_path=resolve_local_path,
    )


def _normalized_url_identity(reference: str):
    parsed = urlparse(reference)
    if parsed.scheme not in {"http", "https"}:
        return None
    netloc = parsed.netloc.lower()
    path = unquote(parsed.path or "")
    if not path:
        return None
    return parsed.scheme.lower(), netloc, path


def _normalized_local_identity(reference: str, resolve_local_path):
    raw = unquote(str(reference).split("#", 1)[0].strip())
    if not raw:
        return None
    resolved = resolve_local_path(raw)
    if resolved:
        return os.path.realpath(resolved)
    if os.path.isabs(raw):
        return os.path.realpath(raw)
    return None
