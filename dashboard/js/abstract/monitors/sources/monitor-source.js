import { ISubject } from "../interfaces/subject.interface.js";
import { MonitorSnapshot } from "./monitor-snapshot.js";

/**
 * MonitorSource — one monitored thing as an ISubject. refresh() fetches its
 * endpoint, hands the payload to its IQueryResultProcessor, keeps the
 * snapshot, and notifies observers (cards, the tab blinker).
 */
export class MonitorSource extends ISubject {
  /**
   * @param {{key:string, label:string, url:string, view:string, gauge?:string,
   *   presets?: {key:string, label:string}[], preset?: string,
   *   processor: import("../interfaces/query-result-processor.interface.js").IQueryResultProcessor,
   *   runner: import("../fetch/fetch-runner.interface.js").IFetchRunner}} spec
   */
  constructor({
    key,
    label,
    url,
    view,
    gauge = null,
    group = "",
    presets = [],
    preset = null,
    processor,
    runner,
  }) {
    super();
    Object.assign(this, {
      key,
      label,
      url,
      view,
      gauge,
      group,
      presets,
      preset,
      processor,
      runner,
    });
    this.snapshot = new MonitorSnapshot({
      detail: "Waiting for first reading…",
    });
  }

  async refresh() {
    try {
      const payload = await this.runner.run(this.url);
      this.snapshot = this.processor.processQueryResult(this, payload);
    } catch (error) {
      this.snapshot = MonitorSnapshot.failed(error);
    }
    this.notify();
    return this.snapshot;
  }
}
