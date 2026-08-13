"""Typed presentation boundary for the shared Set Category picker.

The picker is injected into both static statement reports and the synthetic
Window/Freezer Scan pages. Its category payload is a real boundary: it is
assembled from the taxonomy, serialized into browser JavaScript, and reused by
the external report injector. Keep validation and asset composition here so
the dashboard server only coordinates the pieces.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field


class PickerCategory(BaseModel):
    """One category the browser can display and select."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    cls: str = Field(default="cat-uncategorized", min_length=1)
    bg: str = Field(default="#BFBFBF", min_length=1)
    fg: str = Field(default="#000000", min_length=1)
    excluded: bool = False


class PickerAssets(BaseModel):
    """The three independently composable assets used by report pages."""

    css: str
    html: str
    clickable_row_css: str


class PickerModule(Protocol):
    CATEGORY_PICKER_CSS: str
    CLICKABLE_ROW_CSS: str

    def render_picker_block(self, categories: Sequence[dict[str, Any]]) -> str:
        """Render the picker template with a validated category payload."""
        raise NotImplementedError


def validated_categories(categories: Sequence[dict[str, Any]]) -> list[PickerCategory]:
    """Validate and normalize the category payload at the HTML boundary."""
    return [PickerCategory.model_validate(category) for category in categories]


def render_assets(
    picker_module: PickerModule,
    categories: Sequence[dict[str, Any]],
) -> PickerAssets:
    """Build picker assets from one validated category palette."""
    models = validated_categories(categories)
    payload = [category.model_dump() for category in models]
    return PickerAssets(
        css=picker_module.CATEGORY_PICKER_CSS,
        html=picker_module.render_picker_block(payload),
        clickable_row_css=picker_module.CLICKABLE_ROW_CSS,
    )


def category_row_css(categories: Sequence[dict[str, Any]]) -> str:
    """Return row-color rules for the synthetic scanner/receipt-only table."""
    return "\n".join(
        "    #verified-transactions tbody tr.%s td { background:%s; color:%s; }"
        % (category.cls, category.bg, category.fg)
        for category in validated_categories(categories)
    )
