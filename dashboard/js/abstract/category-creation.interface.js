/** The category dropdown's action is never a category value sent to a save. */
export const ADD_CATEGORY_VENDOR = "__add_category_vendor__";

/** Validate the explicit creation request before crossing the HTTP boundary. */
export function buildCategoryVendorRequest({
  parentName,
  name,
  vendorKey,
  description,
}) {
  const parentId = Number(/\[(\d+)\]$/.exec(parentName || "")?.[1]);
  if (
    !Number.isSafeInteger(parentId) ||
    parentId <= 0 ||
    !name.trim() ||
    name.trim().length > 100 ||
    !/^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(vendorKey) ||
    vendorKey.length > 100 ||
    !description.trim() ||
    description.trim().length > 500 ||
    /[\r\n]/.test(name + description)
  )
    return null;
  return {
    parent_id: parentId,
    name: name.trim(),
    vendor_key: vendorKey,
    description: description.trim(),
  };
}

/** Accept only a complete saved category and vendor-key response. */
export function readCreatedCategory(raw) {
  if (
    raw?.ok !== true ||
    !Number.isSafeInteger(raw.category?.id) ||
    raw.category.id <= 0 ||
    typeof raw.category.name !== "string" ||
    !raw.category.name.endsWith(` [${raw.category.id}]`) ||
    typeof raw.vendor_key !== "string" ||
    !raw.vendor_key
  )
    return null;
  return raw.category;
}

/** A conflict is a preview, never a successful creation or implicit approval. */
export function readVendorCategoryConflict(raw, request) {
  const conflict = raw?.conflict;
  if (
    raw?.ok !== false ||
    raw.code !== "vendor_category_conflict" ||
    conflict?.vendor_key !== request.vendor_key ||
    !Number.isSafeInteger(conflict.current_category?.id) ||
    conflict.current_category.id <= 0 ||
    typeof conflict.current_category.name !== "string" ||
    !conflict.current_category.name ||
    typeof conflict.proposed_category_name !== "string" ||
    !conflict.proposed_category_name
  )
    return null;
  return conflict;
}
