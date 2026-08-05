"""The one strict base for data crossing a dashboard boundary.

Per the rewrite plan: Pydantic v2 models describe data, ABCs describe
behavior. Everything crossing an Interface, process, persistence, or HTTP
boundary derives from `StrictModel` so unknown fields fail closed, values are
never silently coerced, and DTOs cannot be mutated in flight.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Strict, immutable, extra-forbidding base for boundary data."""

    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
