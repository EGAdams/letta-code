import { levelLed } from "../../abstract/monitors/levels/level-palette.js";
import { ledSvg } from "../../abstract/monitors/svg/led-svg.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/** <monitor-led level|color text size> — the-factory's monitor LED, as SVG. */
export const MonitorLedView = Component({
  html: new URL("./monitor-led.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
})(
  class MonitorLedView extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.slot = $el.querySelector(".led");
      this.render();
    }

    render() {
      const color = this.color || levelLed(this.level);
      this.slot.innerHTML = ledSvg(color, {
        size: Number(this.size) || 14,
        title: this.text || this.level || "",
      });
    }
  },
);
