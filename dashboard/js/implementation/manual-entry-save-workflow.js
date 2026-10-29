/** Save batches through the form's view port; refresh once after success. */
import {
  blankManualEntryFields,
  validateManualEntry,
} from "../abstract/manual-entry.interface.js";
import { verifiedTransactionRowsRegistry } from "../abstract/mounted-widget-registry.js";
import {
  buildStatementEntryPayload,
  readStatementEntryResponse,
  summarizeStatementStore,
  validateStatementRow,
} from "../abstract/statement-breakup.interface.js";

const NEW_VENDOR_OPTION = "__new__";

export class ManualEntrySaveWorkflow {
  /** @param {import("../abstract/manual-entry-save-view.interface.js").ManualEntrySaveView} form */
  constructor(form) {
    this._form = form;
  }

  async saveAll() {
    const form = this._form;
    form._captureCurrentItem();
    // Which rules apply is decided by what the document IS, not by how many
    // rows are on screen: a statement's credits are legitimately negative and
    // its rows are stored by a different tool.
    const validate = form.statementHeader
      ? validateStatementRow
      : validateManualEntry;
    const label = form.statementHeader ? "transaction" : "expense";
    const invalidIndex = form.items.findIndex((item) => !validate(item).valid);
    if (invalidIndex !== -1) {
      form.currentIndex = invalidIndex;
      form._renderCurrentItem();
      form._renderErrors(validate(form.items[invalidIndex]).errors);
      form._setStatus(
        `Fix ${label} ${invalidIndex + 1} of ${form.items.length} before saving.`,
      );
      return;
    }
    if (form.statementHeader) {
      await form._saveStatement();
      return;
    }
    const intakeRef = {
      imagePath: form.imagePathInput.value,
      conversationId: form.conversationId,
    };
    const results = [];
    for (let i = 0; i < form.items.length; i++) {
      form._setStatus(`Saving ${i + 1} of ${form.items.length}…`);
      const result = await form._saveOneItem(form.items[i], intakeRef);
      results.push(result);
      // Save All may run again after the operator moves to another item.
      // Promote a successful insert (including a duplicate match that names
      // its existing row) to stored-item state immediately, so that later
      // saves UPDATE that expense rather than feeding it through the insert
      // pipeline a second time.
      if (result.ok && result.expenseId) {
        form.items[i].expenseId = result.expenseId;
      }
      if (result.ok && result.record) {
        const item = form.items[i];
        const vendorKey =
          item.knownVendorKey === NEW_VENDOR_OPTION
            ? item.newVendorKey
            : item.knownVendorKey;
        if (result.isUpdate) {
          verifiedTransactionRowsRegistry.current?.updateExpense(
            result.record,
            vendorKey,
          );
        } else {
          verifiedTransactionRowsRegistry.current?.addExpense(
            result.record,
            vendorKey,
          );
        }
      }
      if (
        result.ok &&
        result.vendorRemembered?.remembered &&
        result.vendorRemembered.vendorKey
      ) {
        form.items[i].knownVendorKey = result.vendorRemembered.vendorKey;
        form.items[i].newVendorKey = "";
      }
    }
    const failed = results.filter((r) => !r.ok);
    if (failed.length) {
      form._setStatus(
        `${results.length - failed.length} of ${results.length} saved; ` +
          `${failed.length} failed: ${failed.map((f) => f.error).join("; ")}`,
      );
      return;
    }
    const updatedCount = results.filter((r) => r.isUpdate).length;
    const insertedCount = results.length - updatedCount;
    let statusText;
    if (updatedCount && insertedCount) {
      statusText = `${insertedCount} expense(s) saved, ${updatedCount} updated.`;
    } else if (updatedCount) {
      statusText = `${updatedCount} expense(s) updated.`;
    } else {
      statusText = `All ${results.length} expense(s) saved.`;
    }
    const newVendorKeys = results
      .map((r) => r.vendorRemembered)
      .filter((v) => v && v.remembered && v.vendorKey)
      .map((v) => v.vendorKey);
    if (newVendorKeys.length) {
      statusText += ` Remembered new vendor(s): ${newVendorKeys.join(", ")}.`;
      // The dropdown was built from the /api/vendor-keys snapshot at mount
      // time, before this save added to vendor_category.yaml -- reload it
      // now so the vendor just typed is immediately pickable, not just on
      // the next page load.
      await form._loadDropdownOptions();
      form._renderCurrentItem();
    }
    if (form.addExpenseMode) {
      // No reload: there is no document behind this page for a reload to
      // re-render, and the newly saved row is already live in Verified
      // Transactions (see addExpense above) -- the operator just needs a
      // blank form to type the next expense into.
      form.items = [blankManualEntryFields()];
      form.currentIndex = 0;
      form._renderCurrentItem();
      form._setStatus(statusText);
      return;
    }
    // Refresh the document only after the whole batch and dropdown updates.
    this._reload(statusText);
  }

  /**
   * Save All, in statement mode: every corrected row in one call.
   *
   * The counts reported back are the store's own -- it is the thing that knows
   * a "PAYMENT - THANK YOU" line is not an expense and that two of these rows
   * are already on file from their receipts. Reporting anything the form
   * computed itself would be a second, weaker opinion about the same rows.
   */
  async saveStatement() {
    const form = this._form;
    form._setStatus(
      `Storing ${form.items.length} transaction(s) through the statement store…`,
    );
    let result;
    try {
      const json = await form.http.postJSON(
        "/api/manual-statement-entry",
        buildStatementEntryPayload(
          // The store's split_expenses_and_credits needs the WHOLE page's
          // signs to classify a borderline row correctly -- submitting only
          // the reviewable rows would change a mixed-sign page into an
          // all-negative one and could flip its verdict on a row that was
          // never touched. The excluded rows ride along unedited; the store
          // reaches the same "not an expense" verdict on them either way and
          // reports them back as skipped_credits.
          [...form.items, ...form.statementExcludedRows],
          {
            imagePath: form.imagePathInput.value,
            conversationId: form.conversationId,
          },
          form.statementHeader,
        ),
        // Duplicate-checking, vendor resolution and the archive move for a
        // whole page run inside one request.
        { timeout: 180000 },
      );
      result = readStatementEntryResponse(json);
    } catch (err) {
      form._setStatus(
        `Statement save failed: ${err && err.message ? err.message : err}`,
      );
      return;
    }
    const summary = summarizeStatementStore(result);
    if (!result.ok) {
      form._setStatus(
        `Statement not stored: ${result.error || "unknown error"} (${summary})` +
          (result.problems.length ? ` ${result.problems.join("; ")}` : ""),
      );
      return;
    }
    this._reload(
      `${summary}${
        result.problems.length ? ` Notes: ${result.problems.join("; ")}` : ""
      }`,
    );
  }

  _reload(status) {
    this._form._setStatus(`${status} Reloading page…`);
    this._form.doc.location.reload();
  }
}
