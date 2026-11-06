import { worstLevel } from "../../abstract/monitors/levels/level-rank.js";
import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";
import { groupSources } from "./group-sources.js";
import { levelCountsHtml } from "./level-counts-html.js";

/**
 * <all-monitors-page> — the Composite root: one group per catalog group,
 * one <monitor-card> per source, and a header that observes them all.
 */
export const AllMonitorsPage = Component({
  html: new URL("./all-monitors-page.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: ["sources"],
})(
  class AllMonitorsPage extends ComponentBase {
    constructor($el, $host) {
      super($el, $host);
      this.groups = $el.querySelector(".groups");
      this.counts = $el.querySelector(".counts");
      this.worst = $el.querySelector(".worst");
      this._sources = [];
    }

    get sources() {
      return this._sources;
    }

    set sources(sources) {
      for (const s of this._sources) s.detach(this);
      this._sources = sources;
      this.groups.replaceChildren(
        ...groupSources(sources).map((g) => this.groupNode(g)),
      );
      for (const s of sources) s.attach(this);
      this.update();
    }

    groupNode({ name, members }) {
      const section = document.createElement("section");
      section.className = "group";
      const heading = section.appendChild(document.createElement("h3"));
      heading.textContent = name;
      const grid = section.appendChild(document.createElement("div"));
      grid.className = "grid";
      for (const source of members)
        grid.appendChild(document.createElement("monitor-card")).source =
          source;
      return section;
    }

    update() {
      const levels = this._sources.map((s) => s.snapshot.level);
      this.worst.setAttribute("level", worstLevel(levels));
      this.counts.innerHTML = levelCountsHtml(levels);
    }
  },
);
