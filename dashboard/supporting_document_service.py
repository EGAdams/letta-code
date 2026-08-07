from __future__ import annotations

"""Helpers for supporting-document resolution.

This module keeps the distinction between receipt evidence and source-document
evidence explicit so server.py can wire endpoints without owning all of the
policy details itself.
"""

from collections.abc import Mapping
import hashlib
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
    left: str | None,
    right: str | None,
    *,
    resolve_local_path,
) -> bool:
    """Return True when two references point at the same effective document.

    Exact string equality is not enough because the dashboard can encounter the
    same file through different spellings (URL escaping, relative-vs-absolute
    local paths, fragment differences, etc.).
    """

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
    if left_path and right_path and left_path == right_path:
        return True
    left_content = _local_content_identity(left_path) if left_path else None
    right_content = _local_content_identity(right_path) if right_path else None
    return bool(left_content and right_content and left_content == right_content)


def should_suppress_source_document(
    source_reference: str | None,
    receipt_reference: str | None,
    *,
    resolve_local_path,
) -> bool:
    return references_same_underlying_document(
        source_reference,
        receipt_reference,
        resolve_local_path=resolve_local_path,
    )


def build_supporting_document_lookup_key(document, *, kind: str) -> str:
    if not document:
        return normalize_supporting_document_reference(document)
    if not isinstance(document, Mapping):
        return normalize_supporting_document_reference(document)
    if kind == "receipt":
        candidate = document.get("receipt_id") or document.get("id") or document.get("document_id")
        return normalize_supporting_document_reference(candidate)
    source_candidate = document.get("source_document_id") or document.get("source_document")
    source_key = normalize_supporting_document_reference(source_candidate)
    if source_key:
        return source_key
    candidate = document.get("id") or document.get("document_id")
    return normalize_supporting_document_reference(candidate)


def _normalized_url_identity(reference: str) -> tuple[str, str, str] | None:
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


def _local_content_identity(path: str):
    """Return a stable identity for two separately archived copies.

    Scanner intake keeps the staged JPEG and the archived JPEG at different
    paths.  ``realpath`` therefore cannot tell that they are the same paper
    document.  Content identity is deliberately used only after both
    references resolve to local files; it never makes a remote URL guessable.
    """
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.digest()
    except (OSError, TypeError):
        return None