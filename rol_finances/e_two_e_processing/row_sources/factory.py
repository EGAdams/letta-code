"""RowSource factory and Pydantic spec."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from e_two_e_processing.normalizer import RowNormalizer
from e_two_e_processing.row_sources.base import RowSource
from e_two_e_processing.row_sources.xlsx_source import XlsxRowSource


class RowSourceSpec(BaseModel):
    """Pydantic spec for selecting and building a RowSource."""

    kind: Literal["xlsx"] = Field(..., description="Source type")
    path: str = Field(..., description="Path to the source file")
    sheet: Optional[str] = Field(None, description="Optional sheet name")

    @classmethod
    def from_path(cls, path: str, sheet: str | None = None) -> "RowSourceSpec":
        suffix = Path(path).suffix.lower()
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            return cls(kind="xlsx", path=path, sheet=sheet)
        raise ValueError(f"Unsupported source type for {path}")

    def build(self, normalizer: RowNormalizer | None = None) -> RowSource:
        if self.kind == "xlsx":
            return XlsxRowSource(
                path=self.path,
                sheet=self.sheet,
                normalizer=normalizer or RowNormalizer(),
            )
        raise ValueError(f"Unsupported RowSource kind: {self.kind}")