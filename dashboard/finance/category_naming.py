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
to import the other's module to get at it. ``TaxonomyCategoryNamer`` is the
only real implementation; server.py owns the taxonomy it reads and hands the
two lookups in at its composition root.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional


class ICategoryNamer(ABC):
    """Translate between a category row id and its reporting label."""

    @abstractmethod
    def name_for(self, category_id: Optional[int]) -> str:
        """The reporting-category label for a row's category_id ('' if none)."""

    @abstractmethod
    def id_for(self, category_name: str) -> Optional[int]:
        """The category id a label resolves to. Raises ValueError if unknown."""


class TaxonomyCategoryNamer(ICategoryNamer):
    """Adapter: a two-method view of whatever owns the category taxonomy.

    Both directions already exist wherever the Set Category dialog is served;
    this exposes exactly those two and nothing else, so a consumer depends on
    the job rather than on the whole taxonomy object.

    The two lookups are injected rather than imported. server.py owns the real
    taxonomy, and importing it from here would put a module cycle between the
    finance package and the service layer -- the composition root hands them in
    instead.

    Inject *callables that perform the lookup*, not the taxonomy functions
    themselves, when late binding matters. ``_get_expense_edit_repository``
    caches its namer for the process lifetime, so a test that replaces a
    taxonomy function after that cache is warm is only honoured if the injected
    callable re-resolves the function on each call.
    """

    def __init__(
        self,
        label_for: Callable[[Optional[int]], Optional[str]],
        resolve: Callable[[str], tuple[Optional[int], Optional[str]]],
    ) -> None:
        self._label_for = label_for
        self._resolve = resolve

    def name_for(self, category_id: Optional[int]) -> str:
        return self._label_for(category_id) or ''

    def id_for(self, category_name: str) -> Optional[int]:
        name = str(category_name or '').strip()
        if not name:
            return None
        target_id, target_cls = self._resolve(name)
        if target_cls is None:
            raise ValueError(f'Unknown category: {name!r}')
        return target_id
