"""Exact expense categories, separate from the rolled-up report palette."""
from __future__ import annotations

from typing import Callable

from category_taxonomy import ICategoryTaxonomy
from finance.category_naming import ICategoryNamer


class ExpenseCategoryCatalog(ICategoryNamer):
    """One vocabulary for the editor's options and its save resolver.

    Full ancestry distinguishes repeated names; the ID suffix makes even
    duplicate paths unambiguous. Existing report-label callers remain valid.
    """

    def __init__(self, taxonomy: Callable[[], ICategoryTaxonomy],
                 fallback: ICategoryNamer):
        self._taxonomy = taxonomy
        self._fallback = fallback

    def options(self) -> list[dict]:
        nodes = {node.id: node for node in self._taxonomy().all_nodes()}
        options = []
        for node in nodes.values():
            if not node.is_active:
                continue
            path, seen, current = [], set(), node
            while current and current.id not in seen:
                seen.add(current.id)
                path.append(current.name)
                current = nodes.get(current.parent_id)
            label = ' / '.join(reversed(path))
            options.append({'id': node.id, 'name': f'{label} [{node.id}]'})
        return sorted(options, key=lambda option: (option['name'].casefold(), option['id']))

    def name_for(self, category_id):
        return next((option['name'] for option in self.options()
                     if option['id'] == category_id), '')

    def id_for(self, category_name):
        name = str(category_name or '').strip()
        if not name:
            return None
        # Legacy reporting names have no ID suffix. Do not reinterpret their
        # labels, which would alter existing manual-entry/report behaviour.
        if not name.endswith(']'):
            return self._fallback.id_for(name)
        for option in self.options():
            if option['name'] == name:
                return option['id']
        raise ValueError(f'Unknown or inactive category: {name!r}')
