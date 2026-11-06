import { IObserver } from "./interfaces/observer.interface.js";
import { worstLevel } from "./levels/level-rank.js";

/**
 * TabAlertObserver — blinks the "All Monitors" nav tab with the dashboard's
 * own classes: .tab-alert (yellow) for warn, .tab-alert-red for crit.
 * It observes every source and always judges all of them together.
 */
export class TabAlertObserver extends IObserver {
  constructor(tab, sources = []) {
    super();
    this.tab = tab;
    this.sources = sources;
  }

  watch(source) {
    if (!this.sources.includes(source)) this.sources.push(source);
    source.attach(this);
  }

  update() {
    if (!this.tab) return;
    const level = worstLevel(this.sources.map((s) => s.snapshot.level));
    this.tab.classList.toggle("tab-alert-red", level === "crit");
    this.tab.classList.toggle("tab-alert", level === "warn");
    this.tab.dataset.monitorLevel = level;
  }
}
