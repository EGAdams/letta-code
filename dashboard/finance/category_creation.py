"""Create a category and an explicit reusable vendor rule through existing storage."""
import threading

from pydantic import ValidationError

from finance.category_creation_model import CategoryVendorRequest
from finance.category_creation_repository import ICategoryCreator

_creation_lock = threading.Lock()


def create_category_vendor(data, *, creator: ICategoryCreator, lookup_factory,
                           catalog, invalidate):
    try:
        request = CategoryVendorRequest.model_validate(data)
    except ValidationError as exc:
        return {'ok': False, 'error': str(exc)}
    category_id = None
    try:
        # Serialize dashboard requests; the canonical lookup owns YAML formatting
        # and duplicate/forbidden-key rules. Reassignment needs a checked preview.
        with _creation_lock:
            lookup = lookup_factory()
            if request.vendor_key in lookup.vendor_map:
                existing_id = lookup.vendor_map[request.vendor_key]
                # Validate the parent too, rather than accept a same-name child
                # under an unrelated branch on a repeated submission.
                parent_name = catalog.name_for(request.parent_id)
                expected_name = parent_name.rsplit(' [', 1)[0] + f' / {request.name} [{existing_id}]'
                expected = next((row for row in catalog.options()
                    if row['id'] == existing_id and row['name'] == expected_name), None)
                if not expected:
                    if request.expected_vendor_category_id != existing_id:
                        current_name = catalog.name_for(existing_id)
                        proposed_name = parent_name.rsplit(' [', 1)[0] + f' / {request.name}'
                        return {'ok': False, 'code': 'vendor_category_conflict',
                                'error': f'That vendor key already belongs to {current_name}. '
                                         'Confirm below to move its future matching rule.',
                                'conflict': {'vendor_key': request.vendor_key,
                                             'current_category': {'id': existing_id, 'name': current_name},
                                             'proposed_category_name': proposed_name}}
                else:
                    return {'ok': True, 'category': expected, 'vendor_key': request.vendor_key}
            elif request.expected_vendor_category_id is not None:
                raise ValueError('That vendor rule was removed. Reload before retrying.')
            category_id = creator.get_or_create(request.parent_id, request.name)
            invalidate()
            if request.expected_vendor_category_id is not None:
                saved = lookup.reassign_vendor_key(request.vendor_key, category_id,
                    expected_category_id=request.expected_vendor_category_id)
            else:
                saved = lookup.add_vendor_key(request.vendor_key, category_id,
                                             raw_description=request.description)
            if not saved:
                raise ValueError('The vendor store refused this key. Choose a different key.')
        return {'ok': True, 'category': {'id': category_id, 'name': catalog.name_for(category_id)},
                'vendor_key': request.vendor_key}
    except Exception as exc:
        prefix = ('The category was saved, but the vendor key was not saved. '
                  'Retry to reuse that category. ' if category_id is not None else '')
        return {'ok': False, 'error': prefix + str(exc)}
