"""Validated input for the editor's explicit category/vendor creation action."""
from pydantic import Field, field_validator

from contracts import StrictModel


class CategoryVendorRequest(StrictModel):
    parent_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    vendor_key: str = Field(min_length=1, max_length=100,
                            pattern=r'^[a-z0-9]+(?:_[a-z0-9]+)*$')
    description: str = Field(min_length=1, max_length=500)
    expected_vendor_category_id: int | None = Field(default=None, gt=0)

    @field_validator('name', 'description')
    @classmethod
    def single_line(cls, value):
        if not value.strip() or '\n' in value or '\r' in value:
            raise ValueError('Enter a name or description on one line.')
        return value.strip()
