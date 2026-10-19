import {
  type BrowserCommand,
  type BrowserOutcome,
  type WorkResult,
} from "./contracts.js";
import type { JsonHttp, Workflows } from "./interfaces.js";
export declare class DashboardWorkflows implements Workflows {
  private readonly http;
  private readonly client;
  constructor(http: JsonHttp, client: string);
  state(): Promise<WorkResult>;
  claim(command: BrowserCommand): Promise<boolean>;
  verify(command: BrowserCommand, outcome: BrowserOutcome): Promise<WorkResult>;
  cancel(command: BrowserCommand): Promise<WorkResult>;
  private decode;
}
