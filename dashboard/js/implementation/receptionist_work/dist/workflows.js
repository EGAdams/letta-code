import { workFrom } from "./contracts.js";
export class DashboardWorkflows {
  http;
  client;
  constructor(http, client) {
    this.http = http;
    this.client = client;
  }
  async state() {
    return this.decode(await this.http.getJSON("/api/receptionist-work"));
  }
  async claim(command) {
    const result = await this.http.postJSON("/api/receptionist-work/claim", {
      command_id: command.id,
      client_id: this.client,
    });
    return (
      typeof result === "object" &&
      result !== null &&
      "ok" in result &&
      result.ok === true
    );
  }
  async verify(command, outcome) {
    return this.decode(
      await this.http.postJSON(
        "/api/receptionist-work",
        {
          workspace: "toyota",
          request_id: `verify-${command.id}`,
          action: "verify",
          command_id: command.id,
          browser_ok: outcome.ok,
          browser_error: outcome.error,
        },
        { timeout: 100000 },
      ),
    );
  }
  async cancel(command) {
    return this.decode(
      await this.http.postJSON(
        "/api/receptionist-work",
        {
          workspace: "toyota",
          request_id: `cancel-${command.id}`,
          action: "cancel",
          command_id: command.id,
        },
        { timeout: 100000 },
      ),
    );
  }
  decode(raw) {
    const result = workFrom(raw);
    if (!result)
      throw new Error("The workflow service returned an invalid checkpoint.");
    return result;
  }
}
