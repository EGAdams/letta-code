import { levelLed } from "../../abstract/monitors/levels/level-palette.js";
import { ledSvg } from "../../abstract/monitors/svg/led-svg.js";
import { esc } from "../../abstract/monitors/svg/svg-escape.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/** <alert-list limit="8"> — one SVG LED row per snapshot item, worst kept in view. */
export const AlertList = Component({
  html: new URL("./alert-list.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["snapshot"],
})(
  class AlertList extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.rows = $el.querySelector(".rows");
    }

    set snapshot(s) {
      const limit = Number(this.limit) || 8;
      const rows = s.items
        .slice(0, limit)
        .map(
          (item) =>
            `<li class="${esc(item.level)}">` +
            ledSvg(levelLed(item.level), { size: 10, title: item.level }) +
            `<span class="label">${esc(item.label)}</span><span class="text">${esc(item.text)}</span></li>`,
        );
      if (s.items.length > limit)
        rows.push(`<li class="more">+${s.items.length - limit} more</li>`);
      this.rows.innerHTML = rows.join("");
      this.$host.hidden = rows.length === 0;
    }

    render() {}
  },
);
