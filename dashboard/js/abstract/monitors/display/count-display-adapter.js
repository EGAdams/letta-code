import { DisplayAdapter } from "./display-adapter.js";

/** Writes a whole count ("3") or "—" into a text element. */
export class CountDisplayAdapter extends DisplayAdapter {
  constructor(element) {
    super();
    this.element = element;
  }

  update(currentValue) {
    this.element.textContent = Number.isFinite(currentValue)
      ? String(Math.round(currentValue))
      : "—";
  }
}
