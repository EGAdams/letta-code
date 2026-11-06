import { createDisplayAdapter } from "../../abstract/monitors/display/display-adapter-factory.js";
import { MonitorViewUpdater } from "../../abstract/monitors/display/monitor-view-updater.js";
import { GaugeFactory } from "../../abstract/monitors/gauges/gauge-factory.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/**
 * <radial-gauge-view gauge-type="…"> — Oak Ridge's gauge building in a card:
 * GaugeFactory.createGauge(type) on a canvas, then draw(), then a
 * MonitorViewUpdater feeds it and its DisplayAdapter each snapshot.
 */
export const RadialGaugeView = Component({
  html: new URL("./radial-gauge-view.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["snapshot"],
})(
  class RadialGaugeView extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.canvas = $el.querySelector("canvas");
      this.reading = $el.querySelector(".reading");
      this.updater = null;
      this._snapshot = null;
    }

    attributeChangedCallback(name, _old, value) {
      if (name !== "gauge-type" || this.updater) return;
      const gauge = GaugeFactory.createGauge(value, this.canvas);
      gauge.draw();
      this.updater = new MonitorViewUpdater(
        gauge,
        createDisplayAdapter(value, this.reading),
      );
      this.render();
    }

    get snapshot() {
      return this._snapshot;
    }
    set snapshot(snapshot) {
      this._snapshot = snapshot;
      this.render();
    }

    render() {
      if (this.updater && this._snapshot)
        this.updater.updateView(this._snapshot.value);
    }
  },
);
