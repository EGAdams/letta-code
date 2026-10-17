/** Category choice and its separate, explicit creation form. No expense writes. */
import {
  ADD_CATEGORY_VENDOR,
  buildCategoryVendorRequest,
  readCreatedCategory,
  readVendorCategoryConflict,
} from "../abstract/category-creation.interface.js";
import { categoryOptionLabels } from "../abstract/category-option-labels.js";
import { readCategoriesResponse } from "../abstract/manual-entry.interface.js";

export class ExpenseCategoryPicker {
  constructor({ http, doc, root, select, categoryNames, description }) {
    Object.assign(this, {
      http,
      doc,
      root,
      select,
      categoryNames,
      description,
    });
    select.classList.add("expense-category-select");
    this.created = new Map();
    this.loadedNames = [];
    this.previous = "";
    select.addEventListener("change", () => {
      if (select.value === ADD_CATEGORY_VENDOR) {
        select.value = this.previous;
        this.open();
      } else this.previous = select.value;
    });
  }

  names() {
    return [
      ...new Set([
        ...this.categoryNames(),
        ...this.loadedNames,
        ...this.created.values(),
      ]),
    ];
  }

  nameForId(id) {
    return this.created.get(id) || "";
  }

  setValue(value) {
    this.select.value = value;
    this.previous = value;
  }

  renderOptions() {
    const selected = this.select.value;
    this.select.innerHTML = "";
    this.option(
      this.select,
      "Add a new category and vendor key…",
      ADD_CATEGORY_VENDOR,
    );
    this.option(this.select, "— leave unresolved —", "");
    const names = this.names();
    if (
      selected &&
      selected !== ADD_CATEGORY_VENDOR &&
      !this.names().includes(selected)
    ) {
      names.push(selected);
    }
    for (const { label, value } of categoryOptionLabels(names))
      this.option(this.select, label, value);
    this.setValue(selected === ADD_CATEGORY_VENDOR ? "" : selected);
  }

  async open() {
    if (!this.form) this.renderForm();
    this.descriptionInput.value = this.description();
    this.status.textContent = "";
    this.clearConfirmation();
    this.form.style.display = "";
    // The same editor can be embedded beside manual entry, whose category
    // vocabulary is only report headings. Always load exact parent choices.
    try {
      this.loadedNames = readCategoriesResponse(
        await this.http.getJSON("/api/expense-categories"),
      );
    } catch {
      /* Existing exact options still work during a refresh failure. */
    }
    this.parentSelect.innerHTML = "";
    this.option(this.parentSelect, "— choose the parent category —", "");
    for (const { label, value } of categoryOptionLabels(
      this.names().filter((name) => /\[\d+\]$/.test(name)),
    )) {
      this.option(this.parentSelect, label, value);
    }
    this.parentSelect.value = this.select.value;
  }

  close() {
    if (this.form) this.form.style.display = "none";
    this.clearConfirmation();
  }

  clearConfirmation() {
    this.pendingMove = null;
    if (this.moveButton) this.moveButton.style.display = "none";
  }

  renderForm() {
    this.form = this.doc.createElement("fieldset");
    this.form.dataset.component = "category-vendor-create";
    this.root.appendChild(this.form);
    const legend = this.doc.createElement("legend");
    legend.textContent = "Add a new category and vendor key";
    this.form.appendChild(legend);
    this.parentSelect = this.field("Put the category under", "select");
    this.parentSelect.classList.add("expense-category-select");
    this.nameInput = this.field(
      "New category name (example: Computer supplies)",
    );
    this.vendorInput = this.field("Vendor key (example: office_supplier)");
    this.descriptionInput = this.field("Merchant / description to recognize");
    this.status = this.doc.createElement("p");
    this.status.role = "status";
    this.form.appendChild(this.status);
    const note = this.doc.createElement("p");
    note.textContent =
      "This saves a category and a vendor rule for future matching. " +
      "Then click Save Changes to apply the category to this expense.";
    this.form.appendChild(note);
    this.saveButton = this.button("Add category and vendor key", () =>
      this.save(),
    );
    this.moveButton = this.button("Create category and move vendor rule", () =>
      this.save(true),
    );
    this.moveButton.style.display = "none";
    this.cancelButton = this.button("Cancel", () => this.close());
  }

  async save(confirmMove = false) {
    const request = buildCategoryVendorRequest({
      parentName: this.parentSelect.value,
      name: this.nameInput.value,
      vendorKey: this.vendorInput.value,
      description: this.descriptionInput.value,
    });
    if (!request) {
      this.status.textContent =
        "Choose a parent, enter a category name and merchant, " +
        "and use lowercase letters, numbers and underscores for the vendor key.";
      return;
    }
    const fingerprint = JSON.stringify(request);
    if (confirmMove && this.pendingMove?.fingerprint === fingerprint) {
      request.expected_vendor_category_id = this.pendingMove.categoryId;
    }
    this.clearConfirmation();
    this.saveButton.disabled = true;
    this.moveButton.disabled = true;
    this.cancelButton.disabled = true;
    this.status.textContent = "Saving category and vendor key…";
    try {
      const raw = await this.http.postJSON(
        "/api/expense-category-vendor",
        request,
      );
      const conflict = readVendorCategoryConflict(raw, request);
      if (conflict) {
        this.pendingMove = {
          fingerprint,
          categoryId: conflict.current_category.id,
        };
        this.status.textContent =
          `Vendor key “${conflict.vendor_key}” currently uses ` +
          `${conflict.current_category.name}. Create “${conflict.proposed_category_name}” ` +
          "and move this vendor’s future matching rule there? Existing expenses stay unchanged. " +
          "Click Create category and move vendor rule to confirm, or Cancel.";
        this.moveButton.style.display = "";
        return;
      }
      const category = readCreatedCategory(raw);
      if (!category) {
        this.status.textContent =
          typeof raw?.error === "string"
            ? raw.error
            : "Could not confirm the new category and vendor key. Please retry.";
        return;
      }
      this.created.set(category.id, category.name);
      // Include categories created by other editors since this page opened.
      try {
        this.loadedNames = readCategoriesResponse(
          await this.http.getJSON("/api/expense-categories"),
        );
      } catch {
        /* The confirmed category remains usable if refresh fails. */
      }
      this.renderOptions();
      this.setValue(category.name);
      this.nameInput.value = "";
      this.vendorInput.value = "";
      this.close();
    } catch (error) {
      this.status.textContent = `Could not save: ${error.message || String(error)}. Retry safely.`;
    } finally {
      this.saveButton.disabled = false;
      this.moveButton.disabled = false;
      this.cancelButton.disabled = false;
    }
  }

  field(text, tag = "input") {
    const label = this.doc.createElement("label");
    label.className = "manual-entry-field";
    label.textContent = text;
    const input = this.doc.createElement(tag);
    if (tag === "input") input.type = "text";
    label.appendChild(input);
    this.form.appendChild(label);
    return input;
  }

  option(select, text, value) {
    const option = this.doc.createElement("option");
    option.textContent = text;
    option.value = value;
    select.appendChild(option);
  }

  button(text, handler) {
    const button = this.doc.createElement("button");
    button.textContent = text;
    button.type = "button";
    button.addEventListener("click", handler);
    this.form.appendChild(button);
    return button;
  }
}
