import { levelColor } from "../../abstract/monitors/levels/level-palette.js";
import { sparklineSvg } from "../../abstract/monitors/svg/sparkline-svg.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

const KEEP = 40;

/** <trend-sparkline> — SVG trend of a snapshot's value across the last polls. */
export const TrendSparkline = Component({
  html: new URL("./trend-sparkline.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["snapshot"],
})(
  class TrendSparkline extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.chart = $el.querySelector(".chart");
      this.caption = $el.querySelector(".caption");
      this.history = [];
    }

    set snapshot(s) {
      if (s.value !== null)
        this.history = [...this.history, s.value].slice(-KEEP);
      this.chart.innerHTML = sparklineSvg(this.history, levelColor(s.level));
      this.caption.textContent =
        s.value === null ? "—" : `${Math.round(s.value)} ${s.unit} now`;
    }
  },
);
