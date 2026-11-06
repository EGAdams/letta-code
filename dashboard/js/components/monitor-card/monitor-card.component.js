import { MonitorLed } from "../../abstract/monitors/interfaces/monitor-led.js";
import { MonitorLedData } from "../../abstract/monitors/interfaces/monitor-led-data.js";
import { presetSnapshot } from "../../abstract/monitors/sources/preset-snapshot.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";
import { mountPresetBank } from "./mount-preset-bank.js";
import { VIEW_TAGS } from "./view-tags.js";

/**
 * <monitor-card> — one monitor. It is an IObserver of its MonitorSource:
 * every update() pushes the snapshot into the LED, the body view and the
 * item list (a Composite of small components). A source with `presets`
 * also gets a <push-button-bank> under the body; the pressed button picks
 * which item the body shows, while the LED keeps the whole source's level.
 */
export const MonitorCard = Component({
  html: new URL("./monitor-card.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["source"],
})(
  class MonitorCard extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      const q = (sel) => $el.querySelector(sel);
      Object.assign(this, {
        title: q(".title"),
        age: q(".age"),
        body: q(".body"),
        items: q(".items"),
        detail: q(".detail"),
      });
      this.led = new MonitorLed(q(".led"));
      this.view = null;
      this.preset = null;
      $el.addEventListener("preset-change", (e) => {
        this.preset = e.detail.key;
        this.update(this._source);
      });
    }

    get source() {
      return this._source;
    }

    set source(source) {
      this._source?.detach(this);
      this._source = source;
      this.title.textContent = source.label;
      const tag = VIEW_TAGS[source.view];
      this.body.replaceChildren();
      this.view = tag
        ? this.body.appendChild(document.createElement(tag))
        : null;
      if (this.view && source.gauge)
        this.view.setAttribute("gauge-type", source.gauge);
      this.preset = mountPresetBank(this.body, source);
      source.attach(this);
      this.update(source);
    }

    connectedCallback() {
      this._source?.attach(this);
    }
    disconnectedCallback() {
      this._source?.detach(this);
    }

    update(source) {
      const s = source.snapshot;
      this.led.setLevel(s.level);
      this.led.setLedText(
        new MonitorLedData({
          classObject: this,
          ledText: `${source.label}: ${s.level}`,
        }),
      );
      this.detail.textContent = s.detail;
      this.age.textContent = new Date(s.at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      if (this.view) this.view.snapshot = presetSnapshot(s, this.preset);
      this.items.snapshot = s;
      this.$host.dataset.level = s.level;
    }
  },
);
