import { IFetchRunner } from "./fetch-runner.interface.js";

/** The plain runner: one GET through the dashboard's HttpClient. */
export class FetchRunner extends IFetchRunner {
  /** @param {import("../../http-client.interface.js").HttpClient} http */
  constructor(http, { timeout = 8000 } = {}) {
    super();
    this.http = http;
    this.timeout = timeout;
  }

  async run(url) {
    return this.http.getJSON(url, { timeout: this.timeout });
  }
}
