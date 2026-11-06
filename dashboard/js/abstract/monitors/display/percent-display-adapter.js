import { DisplayAdapter } from "./display-adapter.js";

/** Writes "42%" (or "—") into a text element. */
export class PercentDisplayAdapter extends DisplayAdapter {
  constructor(element) {
    super();
    this.element = element;
  }

  update(currentValue) {
    this.element.textContent = Number.isFinite(currentValue)
      ? `${Math.round(currentValue)}%`
      : "—";
  }
}
