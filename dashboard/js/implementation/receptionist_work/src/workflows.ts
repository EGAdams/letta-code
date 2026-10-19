import {
  type BrowserCommand,
  type BrowserOutcome,
  type WorkResult,
  workFrom,
} from "./contracts.js";
import type { JsonHttp, Workflows } from "./interfaces.js";

export class DashboardWorkflows implements Workflows {
  constructor(
    private readonly http: JsonHttp,
    private readonly client: string,
  ) {}
  async state(): Promise<WorkResult> {
    return this.decode(await this.http.getJSON("/api/receptionist-work"));
  }
  async claim(command: BrowserCommand): Promise<boolean> {
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
  async verify(
    command: BrowserCommand,
    outcome: BrowserOutcome,
  ): Promise<WorkResult> {
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
  async cancel(command: BrowserCommand): Promise<WorkResult> {
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
  private decode(raw: unknown): WorkResult {
    const result = workFrom(raw);
    if (!result)
      throw new Error("The workflow service returned an invalid checkpoint.");
    return result;
  }
}
