"""Port: translating between a category row id and its reporting label.

Two different vocabularies exist for a category and they are easy to confuse:

* the **leaf** name in the categorizer's ``categories_tree.txt`` -- what
  ``VendorCategoryLookup`` knows, e.g. "Housing Gas Bill";
* the **reporting bucket** label the dashboard's Set Category dialog and the
  ``/api/rol-finance-categories`` dropdown are built from, e.g. "Housing
  Payment & Upkeep".

Sending a leaf name to the form silently does nothing -- the browser drops a
``<select>`` value that matches no ``<option>``, so a perfectly-resolved vendor
still left the Category dropdown blank with no error anywhere (found
2026-08-17). Anything that resolves a category for the UI translates through
this port instead of passing whichever name it happened to be holding.

Lives in its own module because it now has two unrelated consumers (the Edit
Expense repository and the OCR-prefill vendor match), and neither should have
to import the other's module to get at it. server.py owns the only real
implementation, wired at its composition root.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ICategoryNamer(ABC):
    """Translate between a category row id and its reporting label."""

    @abstractmethod
    def name_for(self, category_id: Optional[int]) -> str:
        """The reporting-category label for a row's category_id ('' if none)."""

    @abstractmethod
    def id_for(self, category_name: str) -> Optional[int]:
        """The category id a label resolves to. Raises ValueError if unknown."""
