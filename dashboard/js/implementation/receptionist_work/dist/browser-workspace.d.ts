import type { BrowserCommand, BrowserOutcome, WorkState } from "./contracts.js";
import type { BrowserWorkspace, WorkPresenter } from "./interfaces.js";
/** Adapter to a visible, same-origin browser workspace. No hidden DB writes. */
export declare class DashboardBrowserWorkspace implements BrowserWorkspace {
  private readonly root;
  private readonly doc;
  private readonly presenter;
  private readonly status;
  private readonly history;
  private readonly runs;
  private readonly frame;
  private readonly facts;
  constructor(root: HTMLElement, doc: Document, presenter?: WorkPresenter);
  show(state: WorkState): void;
  /** Each row is labelled, so no condition can be mistaken for another by skimming. */
  private describe;
  execute(command: BrowserCommand): Promise<BrowserOutcome>;
  private load;
}
