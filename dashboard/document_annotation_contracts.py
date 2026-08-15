"""Core contracts for non-destructive supporting-document annotation.

This module deliberately contains no filesystem, subprocess, image, or dashboard
framework dependencies. Format and service adapters depend on these contracts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


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


@dataclass(frozen=True)
class ImageRegionMatch:
    region: tuple[float, float, float, float]
    confidence: float


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


class IImageRegionFallbackMatcher(ABC):
    """Port for a confidence-scored image-region recovery strategy."""

    @abstractmethod
    def find_region(
        self,
        source_path: str,
        evidence: ExpenseEvidence,
    ) -> ImageRegionMatch | None:
        """Return one confident candidate region, or no match."""
