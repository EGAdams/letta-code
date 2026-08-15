import { describe, expect, test } from "bun:test";
import { REVIEW_KIND } from "../abstract/statement-review.interface.js";
import { StatementReviewActions } from "../abstract/statement-review-actions.interface.js";
import { StatementReviewDialog } from "../implementation/statement-review-dialog.js";
import { FakeDocument } from "./_fake-dom.js";

const workbookItem = {
  id: "sidecar.json",
  kind: REVIEW_KIND.WORKBOOK,
  bank_name: "Bank Of Nowhere",
  message: "Add this card.",
  rows: [],
};

function setup({ isRelevantView } = {}) {
  const doc = new FakeDocument();
  doc.body = doc.createElement("body");
  const dialog = new StatementReviewDialog({
    http: { getJSON: async () => ({ reviews: [workbookItem] }) },
    doc,
    storage: null,
    actions: new StatementReviewActions(),
    ...(isRelevantView ? { isRelevantView } : {}),
  });
  return { dialog, doc };
}

describe("StatementReviewDialog view scoping", () => {
  test("defaults to always relevant (existing callers keep the old blocking behavior)", async () => {
    const { dialog, doc } = setup();
    await dialog.poll();
    expect(doc.body.querySelector("#statement-review-dialog")).not.toBeNull();
  });

  test("stays off the page while isRelevantView() is false, without losing the queued item", async () => {
    const { dialog, doc } = setup({ isRelevantView: () => false });
    await dialog.poll();
    expect(doc.body.querySelector("#statement-review-dialog")).toBeNull();
    expect(dialog.current).not.toBeNull(); // still queued, just not blocking the page
  });

  test("syncVisibility() hides the modal immediately after navigating away, without waiting for the next poll", async () => {
    let relevant = true;
    const { dialog, doc } = setup({ isRelevantView: () => relevant });
    await dialog.poll(); // opens + renders while the Scanner tab is active
    expect(doc.body.querySelector("#statement-review-dialog")).not.toBeNull();

    relevant = false;
    dialog.syncVisibility(); // user switched to e.g. the Agents tab
    expect(doc.body.querySelector("#statement-review-dialog")).toBeNull();
    expect(dialog.current).not.toBeNull(); // still queued for when they come back
  });

  test("syncVisibility() is a no-op when nothing is queued", () => {
    const { dialog, doc } = setup({ isRelevantView: () => true });
    dialog.syncVisibility();
    expect(doc.body.querySelector("#statement-review-dialog")).toBeNull();
  });
});
