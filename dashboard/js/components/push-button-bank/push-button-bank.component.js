import { pushButtonBankSvg } from "../../abstract/monitors/svg/push-button-bank-svg.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

const STEP = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

/**
 * <push-button-bank> — '57 Chevy dash-radio push buttons as an SVG radio
 * group. Pressing one sinks it, pops the others out, and fires a bubbling
 * "preset-change" event with {key}. Arrow keys move between buttons.
 */
export const PushButtonBank = Component({
  html: new URL("./push-button-bank.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["presets", "selected"],
})(
  class PushButtonBank extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.slot = $el.querySelector(".radio");
      this._presets = [];
      this._selected = null;
      this.slot.addEventListener("click", (e) =>
        this.press(e.target.closest?.(".key")?.dataset.key),
      );
      this.slot.addEventListener("keydown", (e) => this.onKey(e));
    }

    get presets() {
      return this._presets;
    }
    set presets(presets) {
      this._presets = presets || [];
      this.slot.innerHTML = pushButtonBankSvg(this._presets, this._selected);
    }

    get selected() {
      return this._selected;
    }
    set selected(key) {
      this._selected = key;
      for (const k of this.slot.querySelectorAll(".key")) {
        const on = k.dataset.key === key;
        k.setAttribute("aria-checked", String(on));
        k.setAttribute("tabindex", on ? "0" : "-1");
      }
    }

    press(key) {
      if (!key || key === this._selected) return;
      this.selected = key;
      this.$host.dispatchEvent(
        new CustomEvent("preset-change", {
          detail: { key },
          bubbles: true,
          composed: true,
        }),
      );
    }

    onKey(e) {
      const keys = this._presets.map((p) => p.key);
      const at = keys.indexOf(this._selected);
      if (e.key === " " || e.key === "Enter") return e.preventDefault();
      if (!(e.key in STEP) || !keys.length) return;
      e.preventDefault();
      this.press(keys[(at + STEP[e.key] + keys.length) % keys.length]);
      this.slot.querySelector(`.key[data-key="${this._selected}"]`)?.focus();
    }
  },
);
