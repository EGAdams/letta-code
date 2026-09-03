/** DOM adapter for the receipt-reading Command buttons and progress track. */
import {
  DEFAULT_RECEIPT_READ_MODEL,
  RECEIPT_READ_ACTIONS,
  RECEIPT_READ_MODELS,
  receiptReadAction,
} from "../abstract/receipt-read.interface.js";

const COMPLETE_BLINK_MS = 900;

export class ReceiptReadControls {
  constructor({
    doc,
    parent,
    createButton,
    onRead,
    showImageButton,
    rightEdgeButton,
    delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  }) {
    this.doc = doc;
    this.parent = parent;
    this.createButton = createButton;
    this.onRead = onRead;
    this.showImageButton = showImageButton;
    this.rightEdgeButton = rightEdgeButton;
    this.delay = delay;
    this.buttons = new Map();
  }

  mount() {
    for (const action of RECEIPT_READ_ACTIONS) {
      const button = this.createButton(
        this.parent,
        action.label,
        `receipt-read-${action.intent}`,
      );
      button.addEventListener("click", () => this.onRead(action.intent));
      this.buttons.set(action.intent, button);
    }

    this.progressShell = this.doc.createElement("div");
    this.progressShell.className = "receipt-read-progress-shell";
    this.progressBar = this.doc.createElement("div");
    this.progressBar.className = "receipt-read-progress";
    this.progressShell.appendChild(this.progressBar);
    this.parent.appendChild(this.progressShell);

    this.modelSelect = this.doc.createElement("select");
    this.modelSelect.dataset.field = "mazdaModel";
    for (const { model, label } of RECEIPT_READ_MODELS) {
      const option = this.doc.createElement("option");
      option.textContent = label;
      option.value = model;
      this.modelSelect.appendChild(option);
    }
    this.modelSelect.value = DEFAULT_RECEIPT_READ_MODEL;
    this.parent.appendChild(this.modelSelect);
    return this;
  }

  button(intent) {
    return this.buttons.get(intent);
  }

  begin(intent) {
    for (const button of this.buttons.values()) button.disabled = true;
    this.button(intent).classList.add("is-pressed");
    this._syncProgressGeometry();
    this.progressBar.classList.remove("is-complete");
    this.progressBar.style.animationDuration = "";
    this.progressShell.style.display = "block";
    this.progressBar.style.width = "0%";
    this.progressBar.style.transition = "none";
    this.progressBar.offsetHeight;
    this.progressBar.style.transition = `width ${receiptReadAction(intent).progressSeconds}s linear`;
    this.progressBar.style.width = "100%";
  }

  async finish(intent, succeeded) {
    if (succeeded) {
      this.progressBar.style.transition = "none";
      this.progressBar.style.width = "100%";
      this.progressBar.style.animationDuration = `${COMPLETE_BLINK_MS}ms`;
      this.progressBar.classList.add("is-complete");
      await this.delay(COMPLETE_BLINK_MS);
    }
    this.resetProgress();
    for (const button of this.buttons.values()) button.disabled = false;
    this.button(intent).classList.remove("is-pressed");
  }

  resetProgress() {
    this.progressBar.classList.remove("is-complete");
    this.progressBar.style.animationDuration = "";
    this.progressBar.style.transition = "none";
    this.progressBar.style.width = "0%";
    this.progressShell.style.display = "none";
  }

  _syncProgressGeometry() {
    const rightButton = this.rightEdgeButton();
    if (
      typeof this.parent?.getBoundingClientRect !== "function" ||
      typeof this.showImageButton?.getBoundingClientRect !== "function" ||
      typeof rightButton?.getBoundingClientRect !== "function"
    ) {
      return;
    }
    const parentRect = this.parent.getBoundingClientRect();
    const startRect = this.showImageButton.getBoundingClientRect();
    const endRect = rightButton.getBoundingClientRect();
    const left = startRect.left - parentRect.left;
    const width = Math.max(0, endRect.right - startRect.left);
    if (!Number.isFinite(left) || !Number.isFinite(width) || width <= 0) return;
    this.progressShell.style.marginLeft = `${Math.max(0, left)}px`;
    this.progressShell.style.width = `${width}px`;
  }
}
