"""Keeping every row on one receipt pointed at its newly renamed image.

``update_recent_receipt_references`` is the implementation behind
``server._update_recent_receipt_references``, called by
``RecentReportImageSynchronizer`` (via ``server._synchronize_recent_report_image``)
whenever a receipt file gets renamed. ``get_connection`` stays behind in
server.py -- the live MySQL connection factory, shared and reused far beyond
this module.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable

from finance.expense_schema import InformationSchemaProbe


@dataclass(frozen=True)
class Collaborators:
    """What stays behind in server.py, handed over per call."""

    get_connection: Callable


def update_recent_receipt_references(deps: Collaborators, expense_ids, path, old_path=''):
    """Synchronizes expenses.id_light, receipt_url, and source_file only when
    source_file references the same old receipt (matching old_path basename),
    and matching receipt_metadata.id_light exists.
    """
    ids = tuple(dict.fromkeys(int(value) for value in expense_ids if int(value) > 0))
    if not ids:
        return
    with deps.get_connection() as cnx:
        with cnx.cursor() as cur:
            schema = InformationSchemaProbe().read(
                cur, ('receipt_url', 'source_file', 'id_light', 'receipt_metadata'))

            # Read current state for conditional updates
            placeholders = ','.join(['%s'] * len(ids))
            select_parts = ['id']
            if schema.has('source_file'):
                select_parts.append('source_file')
            if schema.has('id_light'):
                select_parts.append('id_light')
            if schema.has('receipt_metadata'):
                select_parts.append('receipt_metadata')

            cur.execute(
                f"SELECT {', '.join(select_parts)} FROM expenses "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            current_rows = {int(row['id']): row for row in cur.fetchall()}

            # Build new id_light from the new path
            new_basename = os.path.basename(path)
            new_id_light = os.path.splitext(new_basename)[0]
            old_basename = os.path.basename(old_path) if old_path else ''

            # Update each row conditionally
            for expense_id in ids:
                row = current_rows.get(expense_id)
                if not row:
                    continue

                # Only update if source_file matches old receipt
                current_source = str(row.get('source_file') or '')
                if old_basename and current_source:
                    # Check if source_file references the same old receipt
                    if os.path.basename(current_source) != old_basename:
                        continue

                # Check receipt_metadata against the pre-rename identity. The
                # repository may already have written expenses.id_light by the
                # time this aggregate-image synchronization runs; comparing to
                # that new value was the stale-ID ordering bug.
                current_id_light = str(row.get('id_light') or '')
                old_id_light = os.path.splitext(old_basename)[0]
                receipt_metadata = row.get('receipt_metadata') or ''
                try:
                    metadata = json.loads(receipt_metadata) if receipt_metadata else {}
                except (ValueError, TypeError):
                    metadata = {}

                metadata_id_light = str(metadata.get('id_light') or '')

                # Only update if metadata id_light matches current id_light
                if schema.has('id_light') and schema.has('receipt_metadata'):
                    owned_id_light = old_id_light or current_id_light
                    if metadata_id_light and owned_id_light and metadata_id_light != owned_id_light:
                        continue

                # Build update for this specific row
                assignments = []
                values = []

                if schema.has('receipt_url'):
                    assignments.append('receipt_url = %s')
                    values.append(new_basename)

                if schema.has('source_file'):
                    assignments.append('source_file = %s')
                    values.append(path)

                if schema.has('id_light'):
                    assignments.append('id_light = %s')
                    values.append(new_id_light)

                if schema.has('receipt_metadata') and metadata:
                    metadata['id_light'] = new_id_light
                    assignments.append('receipt_metadata = %s')
                    values.append(json.dumps(metadata))

                if assignments:
                    cur.execute(
                        f"UPDATE expenses SET {', '.join(assignments)} WHERE id = %s",
                        tuple(values) + (expense_id,),
                    )

            cnx.commit()
