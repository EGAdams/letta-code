import { levelColor } from "../../abstract/monitors/levels/level-palette.js";
import { durationLabel } from "../../abstract/monitors/svg/duration-label.js";
import { ringSvg } from "../../abstract/monitors/svg/ring-svg.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/** <countdown-ring> — SVG ring of the wait left before the next check/sync. */
export const CountdownRing = Component({
  html: new URL("./countdown-ring.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["snapshot"],
})(
  class CountdownRing extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.chart = $el.querySelector(".chart");
      this.caption = $el.querySelector(".caption");
    }

    set snapshot(s) {
      this.chart.innerHTML = ringSvg(
        s.fraction,
        levelColor(s.level),
        durationLabel(s.value),
      );
      this.caption.textContent =
        s.value === null ? "no schedule" : "until next";
    }
  },
);
