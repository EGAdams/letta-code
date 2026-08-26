"""Shared access to rol_finances' VendorCategoryLookup.

Factored out of server.py so both server.py (the "pick a vendor" dialog for
NEEDS_VENDOR_KEY receipts) and finance/manual_entry.py (OCR-prefill vendor
matching) can use it without a circular import -- manual_entry is imported
BY server.py, so a helper server.py owned couldn't be shared with it.
"""
import os
import sys

CATEGORIZER_LIB_DIR = os.path.expanduser('~/rol_finances/tools/categorizer/python_libary')


def vendor_category_lookup():
    if CATEGORIZER_LIB_DIR not in sys.path:
        sys.path.insert(0, CATEGORIZER_LIB_DIR)
    from vendor_category_lookup import VendorCategoryLookup  # type: ignore
    return VendorCategoryLookup()


def normalize_vendor_slug(description: str) -> str:
    """rol_finances' own description -> vendor_key normalization.

    Imported rather than reimplemented: `_slugify` is the same normalization
    `parse_and_categorize.py` files transactions with, so a key guessed here
    matches a key stored there. It is underscore-private upstream and there is
    no public equivalent -- `find_vendor_match` only resolves vendors that are
    already known, and this runs precisely when one is not. The private name is
    the honest coupling; if it is ever renamed this raises ImportError on the
    first call rather than returning a subtly different slug.
    """
    if CATEGORIZER_LIB_DIR not in sys.path:
        sys.path.insert(0, CATEGORIZER_LIB_DIR)
    from vendor_category_lookup import _slugify  # type: ignore
    return _slugify(description)


def guess_vendor_key(description: str) -> str:
    """Use existing normalization, then trim an obvious statement store id."""
    value = normalize_vendor_slug(description)
    tokens = [token for token in value.split('_') if token]
    for index, token in enumerate(tokens):
        if token.isdigit():
            end = index
            if index and tokens[index - 1] in {'store', 'number', 'no'}:
                end -= 1
            return '_'.join(tokens[:end]) or value
    return value


def remember_vendor(description: str, category_id: int, vendor_key: str):
    """Persist one human-approved rule through the existing lookup service."""
    return vendor_category_lookup().remember(
        description, category_id, vendor_key=vendor_key)


def vendor_is_known(vendor_key: str) -> bool:
    """A dropdown vendor is known only once it has a real category."""
    if not vendor_key:
        return False
    return vendor_category_lookup().vendor_map.get(vendor_key) is not None
