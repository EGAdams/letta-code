"""Non-destructive expense highlighting for supporting documents.

The dashboard depends on ``IExpenseDocumentAnnotationService``.  File-format
details live behind ``IExpenseDocumentAnnotator`` strategies and are wired only
by ``build_document_annotation_service`` (the composition root).
"""

from __future__ import annotations

import hashlib
import os
import re
import statistics
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence

ANNOTATION_SCHEMA_VERSION = 4


@dataclass(frozen=True)
class ExpenseEvidence:
    expense_id: int
    expense_date: str = ""
    amount: str = ""
    description: str = ""
    vendor_key: str = ""
    related_document_path: str = ""
    reference_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnotationResult:
    path: str
    highlighted: bool
    reason: str = ""
    page: int | None = None


class IExpenseDocumentAnnotator(ABC):
    """Strategy port implemented by one or more document formats."""

    @abstractmethod
    def supports(self, source_path: str) -> bool:
        """Return whether this strategy owns ``source_path``."""

    @abstractmethod
    def annotate(
        self,
        source_path: str,
        output_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        """Write an annotated copy, or return a fail-closed no-match result."""


class IExpenseDocumentAnnotationService(ABC):
    """Application port used by the HTTP supporting-document boundary."""

    @abstractmethod
    def prepare(
        self,
        source_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        """Return a viewable annotated copy when the expense can be located."""


class IExpenseReferenceResolver(ABC):
    """Port for deriving stable row identifiers from related evidence."""

    @abstractmethod
    def resolve(self, evidence: ExpenseEvidence) -> tuple[str, ...]:
        """Return identifiers such as a check number, or an empty tuple."""


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _token_list(value: str) -> list[str]:
    """Usable tokens in printed order — the payee comes before its city."""
    seen: list[str] = []
    for token in _TOKEN_RE.findall(str(value or "").lower()):
        if len(token) > 2 and token not in {"the", "and", "for", "inc", "llc"}:
            if token not in seen:
                seen.append(token)
    return seen


def _tokens(value: str) -> set[str]:
    return set(_token_list(value))


def _payee_head_tokens(description: str) -> set[str]:
    """The first tokens of a description — the payee's own name.

    A statement prints "PAYEE CITY STATE", so the trailing tokens are shared by
    every row from the same town ("GRAND RAPIDS MI") and identify nothing. Only
    the head is identity.
    """
    return set(_token_list(description)[:2])


def _amount_decimal(value: object) -> Decimal | None:
    raw = str(value or "").strip().replace("$", "").replace(",", "")
    raw = raw.strip("()")
    try:
        return abs(Decimal(raw))
    except (InvalidOperation, ValueError):
        return None


def _amount_matches(text: str, amount: Decimal | None) -> bool:
    if amount is None:
        return False
    number = f"{amount:.2f}"
    whole, cents = number.split(".")
    grouped = f"{int(whole):,}.{cents}"
    # Avoid matching 25.00 inside 125.00 or an account/reference number.
    return bool(
        re.search(
            rf"(?<![\d.])(?:-\s*|\(\s*)?\$?\s*(?:{re.escape(number)}|"
            rf"{re.escape(grouped)})(?!\d)",
            text,
            re.I,
        )
    )


def _date_variants(value: str) -> set[str]:
    raw = str(value or "").strip()
    parsed = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return {raw.lower()} if raw else set()
    return {
        parsed.strftime("%Y-%m-%d"),
        parsed.strftime("%m/%d/%Y"),
        parsed.strftime("%m/%d/%y"),
        parsed.strftime("%m/%d"),
        parsed.strftime("%m-%d-%Y"),
        parsed.strftime("%m-%d-%y"),
        parsed.strftime("%m-%d"),
        f"{parsed.month}/{parsed.day}/{parsed.year}",
        f"{parsed.month}/{parsed.day}/{str(parsed.year)[2:]}",
        f"{parsed.month}/{parsed.day}",
        f"{parsed.month}-{parsed.day}",
    }


def _date_matches(text: str, evidence_date: str) -> bool:
    lowered = text.lower()
    return any(value and value in lowered for value in _date_variants(evidence_date))


def _complete_date_matches(text: str, evidence_date: str) -> bool:
    """Match a printed calendar date, never a bare M/D mentioned in prose."""
    variants = {
        value
        for value in _date_variants(evidence_date)
        if re.search(r"(?:^|[-/])\d{2,4}$", value)
        and value.count("/") + value.count("-") == 2
    }
    lowered = text.lower()
    return any(value and value in lowered for value in variants)


def _statement_row_date_matches(text: str, evidence_date: str) -> bool:
    """Match the bare M/D a credit-card statement row opens with.

    Card statements print the year once, in the billing-cycle header, and start
    every transaction row with ``MM/DD MM/DD`` (posting and transaction date).
    ``_complete_date_matches`` demands a year, so on those scans it can never
    fire and the identity-only path was unreachable — the Choice Privileges
    freezer scan of 2026-07-29 lost its box for exactly this reason. Anchoring
    at the start of the line keeps the looser M/D out of prose, where a
    "payment due by 03/21" sentence would otherwise read as a row date.
    """
    variants = {
        value
        for value in _date_variants(evidence_date)
        if value.count("/") + value.count("-") == 1
    }
    stripped = str(text or "").lstrip(" |[](){}<>*.,:;-_\"'`~")
    return any(value and stripped.lower().startswith(value) for value in variants)


# A tie at or above this score is decisive; below it, two equally-ranked rows
# reject each other rather than boxing the wrong one.
_DECISIVE_SCORE = 10
# Ceiling for a match that never confirmed the amount.  Held below
# ``_DECISIVE_SCORE`` on purpose, so an identity-only win can never survive a
# tie with a second row that looks just as much like this expense.
_IDENTITY_ONLY_CEILING = 9


def _strong_description_score(
    description_tokens: set[str],
    description_hits: int,
) -> int:
    """Score a long, distinctive description when OCR loses date and amount."""
    if len(description_tokens) < 8 or description_hits < 5:
        return -1
    coverage = description_hits / len(description_tokens)
    if coverage < 0.5:
        return -1
    return min(
        _IDENTITY_ONLY_CEILING,
        5 + round(coverage * 4),
    )


def _line_score(text: str, evidence: ExpenseEvidence) -> int:
    amount = _amount_decimal(evidence.amount)
    reference_hit = any(
        re.search(rf"\b{re.escape(term)}\b", text, re.I)
        for term in evidence.reference_terms
        if term
    )
    amount_hit = _amount_matches(text, amount)
    date_hit = _date_matches(text, evidence.expense_date)
    line_tokens = _tokens(text)
    description_tokens = _tokens(evidence.description)
    description_hits = len(line_tokens & description_tokens)
    vendor_hits = len(line_tokens & _tokens(evidence.vendor_key.replace("_", " ")))
    if not amount_hit and not reference_hit:
        # A scan EG has written on loses its amount column to OCR: the pen
        # stroke crosses the digits and "10.59" comes back as "1.59" or noise.
        # Rather than fail closed on the whole row, accept the date plus a
        # substantial share of the payee as identity, scored below the
        # decisive band so any rival row still cancels the box.
        # OCR routinely truncates the payee ("RADISSON HO"), so one hit on the
        # payee's own name says more than two on the city it shares with every
        # neighbouring row.
        head_hits = len(line_tokens & _payee_head_tokens(evidence.description))
        tail_hits = description_hits - head_hits
        if _complete_date_matches(text, evidence.expense_date):
            identified = description_hits >= 2
        elif _statement_row_date_matches(text, evidence.expense_date):
            # A bare M/D is weaker evidence than a printed calendar date, so
            # require the payee's head: geography alone must never win a row.
            identified = head_hits >= 1
        else:
            identified = False
        if identified:
            return min(
                _IDENTITY_ONLY_CEILING,
                5 + 2 * min(head_hits, 2) + min(tail_hits, 2)
                + min(vendor_hits, 2),
            )
        return _strong_description_score(description_tokens, description_hits)
    score = 12 if reference_hit else 0
    if amount_hit:
        score += 5
    if date_hit:
        score += 5
    score += min(description_hits, 3)
    score += min(vendor_hits, 2)
    return score


def _amount_confirmed(text: str, evidence: ExpenseEvidence) -> bool:
    """Whether this line proves the amount itself, not just the expense's identity."""
    return _amount_matches(text, _amount_decimal(evidence.amount))


def _region_bounds(region: object) -> tuple[object, float, float] | None:
    """``(page, top, bottom)`` for a candidate region, or ``None`` if unknown."""
    if not isinstance(region, tuple) or not region:
        return None
    if len(region) == 4 and all(
        isinstance(value, (int, float)) for value in region
    ):
        # Image strategy: (left, top, right, bottom) on a single-page image.
        return "", float(region[1]), float(region[3])
    head, rest = region[0], region[1:]
    if len(rest) == 1 and all(hasattr(rest[0], side) for side in ("y0", "y1")):
        # PDF strategy: (page index, Rect).
        return head, float(rest[0].y0), float(rest[0].y1)
    if len(rest) == 3 and isinstance(rest[0], (int, float)):
        # Excel strategy: (sheet, row number, first column, last column).
        return repr(head), float(rest[0]), float(rest[0])
    return None


def _same_row(first: object, second: object) -> bool:
    """Whether two candidates are one physical row enumerated twice.

    Every strategy describes a row more than once on purpose — word-grouped
    and spatially reconstructed, plus an amount/date pair for PDFs — so two
    top-ranked candidates are usually the same row seen twice.  Only a tie
    between genuinely different rows is the ambiguity the tie rule exists for.
    """
    left = _region_bounds(first)
    right = _region_bounds(second)
    if left is None or right is None:
        return first == second
    if left[0] != right[0]:
        return False
    overlap = min(left[2], right[2]) - max(left[1], right[1])
    span = min(left[2] - left[1], right[2] - right[1])
    if span <= 0:
        return overlap >= 0
    return overlap > span / 2


def _best_line(
    lines: Iterable[tuple[str, object]],
    evidence: ExpenseEvidence,
) -> tuple[object | None, int, str]:
    """Return ``(region, score, text)`` for the winning line, or ``(None, …)``."""
    ranked = sorted(
        (
            (_line_score(text, evidence), region, text)
            for text, region in lines
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked:
        return None, -1, ""
    if ranked[0][0] < 7:
        # The date/vendor corroboration this document offers is too thin to
        # clear the normal bar — but if the target amount appears on exactly
        # one physical row anywhere in the document, there is no rival row it
        # could be confused with, so that uniqueness alone is enough to box
        # it. This is what a single-item receipt (or an itemized invoice's
        # total line) needs: the total often carries no nearby date or payee
        # text, but its amount is the only occurrence in the document.
        amount = _amount_decimal(evidence.amount)
        matches = [item for item in ranked if _amount_matches(item[2], amount)]
        if matches:
            # Every strategy enumerates one physical row two or three times on
            # purpose (word-grouped, spatially reconstructed, plus wrapped-line
            # windows), so a wrapped row's reconstructed span can overlap both
            # of its own halves without those halves overlapping each other —
            # _same_row is not transitive. Cluster with union-find instead of
            # a single running "already seen" region, so a genuinely single
            # physical row is never miscounted as two just because no pair of
            # its representations happens to overlap directly.
            parents = list(range(len(matches)))

            def _root(i: int) -> int:
                while parents[i] != i:
                    parents[i] = parents[parents[i]]
                    i = parents[i]
                return i

            for i in range(len(matches)):
                for j in range(i + 1, len(matches)):
                    if _same_row(matches[i][1], matches[j][1]):
                        root_i, root_j = _root(i), _root(j)
                        if root_i != root_j:
                            parents[root_i] = root_j
            if len({_root(i) for i in range(len(matches))}) == 1:
                return matches[0][1], matches[0][0], matches[0][2]
        return None, ranked[0][0], ""
    # A date+amount match is decisive.  For looser description matches, reject
    # a tie instead of boxing the wrong repeated amount.
    rival = next(
        (
            item
            for item in ranked[1:]
            if not _same_row(item[1], ranked[0][1])
        ),
        None,
    )
    if (
        ranked[0][0] < _DECISIVE_SCORE
        and rival is not None
        and rival[0] == ranked[0][0]
    ):
        return None, ranked[0][0], ""
    return ranked[0][1], ranked[0][0], ranked[0][2]


def _spatial_lines(
    words: Iterable[tuple[str, float, float, float, float]],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Reconstruct visual rows when document extractors split table columns."""
    clean = [
        (str(text).strip(), float(x0), float(y0), float(x1), float(y1))
        for text, x0, y0, x1, y1 in words
        if str(text).strip()
    ]
    if not clean:
        return []
    heights = [max(1.0, word[4] - word[2]) for word in clean]
    tolerance = max(3.0, statistics.median(heights) * 0.8)
    rows: list[list[tuple[str, float, float, float, float]]] = []
    centers: list[float] = []
    for word in sorted(clean, key=lambda item: ((item[2] + item[4]) / 2, item[1])):
        center = (word[2] + word[4]) / 2
        best = None
        best_distance = None
        for index, row_center in enumerate(centers):
            distance = abs(center - row_center)
            if distance <= tolerance and (
                best_distance is None or distance < best_distance
            ):
                best = index
                best_distance = distance
        if best is None:
            rows.append([word])
            centers.append(center)
        else:
            rows[best].append(word)
            centers[best] = sum(
                (item[2] + item[4]) / 2 for item in rows[best]
            ) / len(rows[best])
    output = []
    for row in rows:
        row.sort(key=lambda item: item[1])
        output.append(
            (
                " ".join(item[0] for item in row),
                (
                    min(item[1] for item in row),
                    min(item[2] for item in row),
                    max(item[3] for item in row),
                    max(item[4] for item in row),
                ),
            )
        )
    return output


def _wrapped_line_windows(
    lines: Sequence[tuple[str, tuple[float, float, float, float]]],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Join overlapping OCR lines from one wrapped table row.

    Tesseract can split a wrapped description into two rows and attach the
    date/amount noise to only one of them. Only vertically touching lines with
    overlapping horizontal bounds are joined, so adjacent table rows remain
    separate candidates and the normal ambiguity rules still apply.
    """
    clean = [
        (
            str(text).strip(),
            tuple(float(value) for value in region),
        )
        for text, region in lines
        if str(text).strip()
        and len(region) == 4
        and all(isinstance(value, (int, float)) for value in region)
    ]
    if len(clean) < 2:
        return []
    heights = [
        max(1.0, region[3] - region[1])
        for _text, region in clean
    ]
    max_gap = max(2.0, statistics.median(heights) * 0.25)
    ordered = sorted(clean, key=lambda item: (item[1][1], item[1][0]))
    windows = []
    for index, (text, region) in enumerate(ordered[:-1]):
        parts = [text]
        left, top, right, bottom = region
        for next_text, next_region in ordered[index + 1:index + 3]:
            horizontal_overlap = min(right, next_region[2]) - max(
                left, next_region[0]
            )
            if next_region[1] > bottom + max_gap or horizontal_overlap <= 0:
                break
            parts.append(next_text)
            left = min(left, next_region[0])
            top = min(top, next_region[1])
            right = max(right, next_region[2])
            bottom = max(bottom, next_region[3])
            windows.append((" ".join(parts), (left, top, right, bottom)))
    return windows


class PdfExpenseDocumentAnnotator(IExpenseDocumentAnnotator):
    def supports(self, source_path: str) -> bool:
        return Path(source_path).suffix.lower() == ".pdf"

    def annotate(
        self,
        source_path: str,
        output_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        try:
            import fitz
        except ImportError:
            return AnnotationResult(source_path, False, "PyMuPDF is not installed.")

        document = fitz.open(source_path)
        candidates: list[tuple[str, tuple[int, object]]] = []
        try:
            for page_index, page in enumerate(document):
                page_words = list(page.get_text("words"))
                amount = _amount_decimal(evidence.amount)
                median_height = statistics.median(
                    max(1.0, word[3] - word[1]) for word in page_words
                ) if page_words else 1.0
                row_tolerance = max(3.0, median_height * 0.8)
                # Table PDFs often encode each cell as a separate "line".
                # Pair the exact amount with the nearest same-row date first;
                # its tight rectangle avoids boxing three side-by-side checks
                # that happen to share one visual y coordinate.
                for amount_word in page_words:
                    if not _amount_matches(str(amount_word[4]), amount):
                        continue
                    amount_center_y = (amount_word[1] + amount_word[3]) / 2
                    same_row = [
                        word
                        for word in page_words
                        if abs(
                            ((word[1] + word[3]) / 2) - amount_center_y
                        ) <= row_tolerance
                    ]
                    dates = [
                        word for word in same_row
                        if _date_matches(str(word[4]), evidence.expense_date)
                    ]
                    if not dates:
                        continue
                    date_word = min(
                        dates,
                        key=lambda word: abs(word[0] - amount_word[0]),
                    )
                    left = min(date_word[0], amount_word[0])
                    right = max(date_word[2], amount_word[2])
                    nearby = [
                        word for word in same_row
                        if left - 75 <= word[0] and word[2] <= right + 8
                    ]
                    rect = fitz.Rect(
                        min(word[0] for word in nearby),
                        min(word[1] for word in nearby),
                        max(word[2] for word in nearby),
                        max(word[3] for word in nearby),
                    )
                    text = " ".join(
                        str(word[4]) for word in sorted(
                            nearby, key=lambda word: word[0])
                    )
                    candidates.append((text, (page_index, rect)))
                grouped: dict[tuple[int, int], list[tuple]] = {}
                for word in page_words:
                    grouped.setdefault((int(word[5]), int(word[6])), []).append(word)
                for words in grouped.values():
                    words.sort(key=lambda word: word[0])
                    text = " ".join(str(word[4]) for word in words)
                    rect = fitz.Rect(
                        min(word[0] for word in words),
                        min(word[1] for word in words),
                        max(word[2] for word in words),
                        max(word[3] for word in words),
                    )
                    candidates.append((text, (page_index, rect)))
                for text, bounds in _spatial_lines(
                    (word[4], word[0], word[1], word[2], word[3])
                    for word in page_words
                ):
                    candidates.append(
                        (text, (page_index, fitz.Rect(*bounds)))
                    )
            region, _score, _text = _best_line(candidates, evidence)
            if region is None:
                return AnnotationResult(
                    source_path,
                    False,
                    "No high-confidence expense row was found in the PDF.",
                )
            page_index, rect = region
            page = document[page_index]
            rect = fitz.Rect(
                max(page.rect.x0, rect.x0 - 4),
                max(page.rect.y0, rect.y0 - 3),
                min(page.rect.x1, rect.x1 + 4),
                min(page.rect.y1, rect.y1 + 3),
            )
            page.draw_rect(rect, color=(1, 0, 0), width=3, overlay=True)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            document.save(output_path, garbage=3, deflate=True)
            return AnnotationResult(output_path, True, page=page_index + 1)
        finally:
            document.close()


class PdfCheckNumberResolver(IExpenseReferenceResolver):
    """Find the check number beside this expense in a related bank statement."""

    def resolve(self, evidence: ExpenseEvidence) -> tuple[str, ...]:
        source_path = evidence.related_document_path
        if not source_path or Path(source_path).suffix.lower() != ".pdf":
            return ()
        try:
            import fitz
        except ImportError:
            return ()
        amount = _amount_decimal(evidence.amount)
        try:
            document = fitz.open(source_path)
        except Exception:
            return ()
        try:
            for page in document:
                words = list(page.get_text("words"))
                if not words:
                    continue
                tolerance = max(
                    3.0,
                    statistics.median(
                        max(1.0, word[3] - word[1]) for word in words
                    ) * 0.8,
                )
                for amount_word in words:
                    if not _amount_matches(str(amount_word[4]), amount):
                        continue
                    center_y = (amount_word[1] + amount_word[3]) / 2
                    row = [
                        word for word in words
                        if abs(((word[1] + word[3]) / 2) - center_y)
                        <= tolerance
                    ]
                    dates = [
                        word for word in row
                        if _date_matches(str(word[4]), evidence.expense_date)
                    ]
                    if not dates:
                        continue
                    date_word = min(
                        dates,
                        key=lambda word: abs(word[0] - amount_word[0]),
                    )
                    identifiers = [
                        str(word[4])
                        for word in row
                        if word[2] <= date_word[0]
                        and date_word[0] - word[2] <= 95
                        and re.fullmatch(r"\d{4,6}", str(word[4]))
                    ]
                    if identifiers:
                        return (identifiers[-1],)
        finally:
            document.close()
        return ()


class ImageExpenseDocumentAnnotator(IExpenseDocumentAnnotator):
    _EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

    def __init__(
        self,
        reference_resolver: IExpenseReferenceResolver | None = None,
    ) -> None:
        self._reference_resolver = reference_resolver

    def supports(self, source_path: str) -> bool:
        return Path(source_path).suffix.lower() in self._EXTENSIONS

    def annotate(
        self,
        source_path: str,
        output_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        try:
            from PIL import Image, ImageDraw
            import pytesseract
            from pytesseract import Output
        except ImportError:
            return AnnotationResult(
                source_path, False, "Pillow or pytesseract is not installed."
            )

        try:
            image = Image.open(source_path)
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
        except Exception as exc:
            return AnnotationResult(
                source_path, False, f"Image OCR was unavailable: {exc}"
            )

        match_evidence = evidence
        if self._reference_resolver is not None:
            terms = self._reference_resolver.resolve(evidence)
            if terms:
                match_evidence = replace(evidence, reference_terms=terms)

        grouped: dict[tuple[int, int, int], list[int]] = {}
        spatial_words = []
        for index, text in enumerate(data.get("text", [])):
            if str(text or "").strip():
                key = (
                    int(data["block_num"][index]),
                    int(data["par_num"][index]),
                    int(data["line_num"][index]),
                )
                grouped.setdefault(key, []).append(index)
                spatial_words.append(
                    (
                        str(text),
                        int(data["left"][index]),
                        int(data["top"][index]),
                        int(data["left"][index]) + int(data["width"][index]),
                        int(data["top"][index]) + int(data["height"][index]),
                    )
                )
        lines = []
        for indexes in grouped.values():
            text = " ".join(str(data["text"][index]) for index in indexes)
            left = min(int(data["left"][index]) for index in indexes)
            top = min(int(data["top"][index]) for index in indexes)
            right = max(
                int(data["left"][index]) + int(data["width"][index])
                for index in indexes
            )
            bottom = max(
                int(data["top"][index]) + int(data["height"][index])
                for index in indexes
            )
            lines.append((text, (left, top, right, bottom)))
        lines.extend(_wrapped_line_windows(lines))
        spatial_lines = _spatial_lines(spatial_words)
        lines.extend(spatial_lines)
        lines.extend(_wrapped_line_windows(spatial_lines))
        region, _score, matched_text = _best_line(lines, match_evidence)
        if region is None:
            return AnnotationResult(
                source_path,
                False,
                "No high-confidence expense row was found in the image.",
            )
        left, top, right, bottom = region
        if match_evidence.reference_terms:
            # A ledger's related statement may identify the expense by check
            # number even when cross-outs defeat OCR on the payment line.
            # Include the payment/confirmation lines immediately above it.
            left = min(left, round(image.width * 0.08))
            right = max(right, round(image.width * 0.94))
            top = max(0, top - round(image.height * 0.06))
            bottom = min(image.height - 1, bottom + round(image.height * 0.01))
        elif not _amount_confirmed(matched_text, match_evidence):
            # Identity-only match: OCR lost the amount column, so the winning
            # line stops short of it.  Box the full statement row so the red
            # box still shows EG where the money came from.
            description_tokens = _tokens(match_evidence.description)
            description_hits = len(
                _tokens(matched_text) & description_tokens
            )
            if _strong_description_score(
                description_tokens, description_hits
            ) < 0:
                left = min(left, round(image.width * 0.08))
            right = max(right, round(image.width * 0.94))
        padding = max(8, round(image.width * 0.004))
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width - 1, right + padding),
                min(image.height - 1, bottom + padding),
            ),
            outline="red",
            width=max(5, round(image.width * 0.003)),
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        suffix = Path(output_path).suffix.lower()
        output_format = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".bmp": "BMP",
            ".tif": "TIFF",
            ".tiff": "TIFF",
            ".webp": "WEBP",
        }.get(suffix, image.format or "PNG")
        if output_format == "JPEG" and image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(output_path, format=output_format)
        return AnnotationResult(output_path, True)


class ExcelExpenseDocumentAnnotator(IExpenseDocumentAnnotator):
    _EXTENSIONS = {".xlsx", ".xlsm"}

    def supports(self, source_path: str) -> bool:
        return Path(source_path).suffix.lower() in self._EXTENSIONS

    def annotate(
        self,
        source_path: str,
        output_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import Border, Side
        except ImportError:
            return AnnotationResult(source_path, False, "openpyxl is not installed.")

        keep_vba = Path(source_path).suffix.lower() == ".xlsm"
        workbook = load_workbook(source_path, keep_vba=keep_vba, data_only=False)
        candidates: list[tuple[str, tuple[object, int, int, int]]] = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                populated = [cell for cell in row if cell.value not in (None, "")]
                if not populated:
                    continue
                text_parts = []
                for cell in populated:
                    value = cell.value
                    if isinstance(value, (datetime, date)):
                        text_parts.append(value.strftime("%m/%d/%Y"))
                    elif isinstance(value, (int, float, Decimal)):
                        text_parts.append(f"{value:.2f}")
                    else:
                        text_parts.append(str(value))
                candidates.append(
                    (
                        " ".join(text_parts),
                        (sheet, row[0].row, populated[0].column, populated[-1].column),
                    )
                )
        region, _score, _text = _best_line(candidates, evidence)
        if region is None:
            workbook.close()
            return AnnotationResult(
                source_path,
                False,
                "No high-confidence expense row was found in the spreadsheet.",
            )
        sheet, row_number, first_column, last_column = region
        red = Side(style="thick", color="FFFF0000")
        for column in range(first_column, last_column + 1):
            cell = sheet.cell(row=row_number, column=column)
            cell.border = Border(
                left=red if column == first_column else cell.border.left,
                right=red if column == last_column else cell.border.right,
                top=red,
                bottom=red,
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        workbook.save(output_path)
        workbook.close()
        return AnnotationResult(output_path, True)


class ExpenseDocumentAnnotationService(IExpenseDocumentAnnotationService):
    def __init__(
        self,
        annotators: Sequence[IExpenseDocumentAnnotator],
        cache_dir: str,
    ) -> None:
        self._annotators = tuple(annotators)
        self._cache_dir = os.path.abspath(cache_dir)
        self._lock = threading.Lock()

    def prepare(
        self,
        source_path: str,
        evidence: ExpenseEvidence,
    ) -> AnnotationResult:
        source_path = os.path.abspath(source_path)
        annotator = next(
            (item for item in self._annotators if item.supports(source_path)), None
        )
        if annotator is None:
            return AnnotationResult(
                source_path, False, "This document format has no annotation strategy."
            )
        try:
            stat = os.stat(source_path)
        except OSError as exc:
            return AnnotationResult(source_path, False, f"Document unavailable: {exc}")
        fingerprint = hashlib.sha256(
            repr(
                (
                    source_path,
                    stat.st_mtime_ns,
                    stat.st_size,
                    evidence,
                    type(annotator).__name__,
                    ANNOTATION_SCHEMA_VERSION,
                )
            ).encode("utf-8")
        ).hexdigest()[:24]
        suffix = Path(source_path).suffix.lower()
        output_path = os.path.join(
            self._cache_dir,
            f"expense-{evidence.expense_id}-{fingerprint}{suffix}",
        )
        if os.path.isfile(output_path):
            return AnnotationResult(output_path, True)
        with self._lock:
            if os.path.isfile(output_path):
                return AnnotationResult(output_path, True)
            try:
                return annotator.annotate(source_path, output_path, evidence)
            except Exception as exc:
                return AnnotationResult(
                    source_path,
                    False,
                    f"Highlighting failed safely: {type(exc).__name__}: {exc}",
                )


def build_document_annotation_service(
    cache_dir: str,
) -> IExpenseDocumentAnnotationService:
    """Composition root: wire format implementations to the application port."""
    return ExpenseDocumentAnnotationService(
        (
            PdfExpenseDocumentAnnotator(),
            ImageExpenseDocumentAnnotator(PdfCheckNumberResolver()),
            ExcelExpenseDocumentAnnotator(),
        ),
        cache_dir,
    )
