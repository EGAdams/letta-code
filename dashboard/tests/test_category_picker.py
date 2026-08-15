import pytest
from pydantic import ValidationError

from category_picker import category_row_css, render_assets


class _PickerModule:
    CATEGORY_PICKER_CSS = "/* picker */"
    CLICKABLE_ROW_CSS = "/* rows */"

    @staticmethod
    def render_picker_block(categories):
        return repr(categories)


def test_picker_assets_validate_the_browser_category_boundary():
    assets = render_assets(
        _PickerModule(),
        [{"name": "Food", "cls": "cat-food", "bg": "#fff", "fg": "#000"}],
    )

    assert assets.css == "/* picker */"
    assert assets.clickable_row_css == "/* rows */"
    assert "'name': 'Food'" in assets.html


def test_picker_rejects_an_empty_category_name():
    with pytest.raises(ValidationError):
        render_assets(_PickerModule(), [{"name": ""}])


def test_category_row_css_uses_the_same_validated_palette():
    css = category_row_css([
        {"name": "Food", "cls": "cat-food", "bg": "#fff", "fg": "#000"},
    ])

    assert ".cat-food td { background:#fff; color:#000; }" in css
