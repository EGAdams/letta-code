import { levelColor } from "../../abstract/monitors/levels/level-palette.js";
import { donutSvg } from "../../abstract/monitors/svg/donut-svg.js";
import { esc } from "../../abstract/monitors/svg/svg-escape.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/** <status-donut> — SVG donut of a snapshot's {label, value, level} segments. */
export const StatusDonut = Component({
  html: new URL("./status-donut.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["snapshot"],
})(
  class StatusDonut extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.chart = $el.querySelector(".chart");
      this.caption = $el.querySelector(".caption");
    }

    set snapshot(s) {
      const segments = s.segments.map((seg) => ({
        ...seg,
        color: levelColor(seg.level),
      }));
      this.chart.innerHTML = donutSvg(segments);
      this.caption.innerHTML = segments
        .map(
          (seg) =>
            `<span class="key"><i style="background:${esc(seg.color)}"></i>${esc(seg.label)} ${seg.value}</span>`,
        )
        .join(" ");
    }
  },
);
