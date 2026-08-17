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
