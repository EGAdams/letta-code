"""Category creation port and MySQL adapter. Never edits expense rows."""
from abc import ABC, abstractmethod


class ICategoryCreator(ABC):
    @abstractmethod
    def get_or_create(self, parent_id: int, name: str) -> int:
        """Reuse an active child with this exact name, or create it."""


class MySqlCategoryCreator(ICategoryCreator):
    def __init__(self, connect):
        self._connect = connect

    def get_or_create(self, parent_id, name):
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM categories WHERE id = %s AND is_active = 1 "
                        "AND retired_at IS NULL AND kind = 'EXPENSE' FOR UPDATE",
                        (parent_id,))
                    if not cursor.fetchone():
                        raise ValueError('Choose an active expense parent category.')
                    cursor.execute(
                        'SELECT id, is_active, retired_at, kind FROM categories '
                        'WHERE parent_id = %s AND name = %s FOR UPDATE',
                        (parent_id, name))
                    children = cursor.fetchall()
                    if len(children) > 1:
                        raise ValueError('Duplicate category names need review first.')
                    if children:
                        child = children[0]
                        if not child['is_active'] or child['retired_at'] or child['kind'] != 'EXPENSE':
                            raise ValueError('That category name is retired. Choose another name.')
                        category_id = int(child['id'])
                    else:
                        cursor.execute(
                            'INSERT INTO categories (parent_id, name, kind, is_selectable, '
                            'functional_class, irs_natural_class, excluded_from_nonprofit_totals, '
                            'per_expense_only) SELECT id, %s, \'EXPENSE\', 1, functional_class, '
                            'irs_natural_class, excluded_from_nonprofit_totals, per_expense_only '
                            'FROM categories WHERE id = %s', (name, parent_id))
                        category_id = int(cursor.lastrowid)
                connection.commit()
                return category_id
            except Exception:
                connection.rollback()
                raise
