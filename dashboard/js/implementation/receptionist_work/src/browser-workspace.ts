import type { BrowserCommand, BrowserOutcome, WorkState } from "./contracts.js";
import type {
  BrowserWorkspace,
  WorkFacts,
  WorkPresenter,
} from "./interfaces.js";
import { TrainingWorkPresenter } from "./presentation.js";

/** Adapter to a visible, same-origin browser workspace. No hidden DB writes. */
export class DashboardBrowserWorkspace implements BrowserWorkspace {
  private readonly status: HTMLElement;
  private readonly history: HTMLOListElement;
  private readonly runs: HTMLElement;
  private readonly frame: HTMLIFrameElement;
  private readonly facts: HTMLDListElement;
  constructor(
    private readonly root: HTMLElement,
    private readonly doc: Document,
    private readonly presenter: WorkPresenter = new TrainingWorkPresenter(),
  ) {
    const title = doc.createElement("h3");
    title.textContent = "Toyota's work — synthetic training";
    this.status = doc.createElement("p");
    this.status.setAttribute("aria-live", "polite");
    this.facts = doc.createElement("dl");
    this.facts.className = "receptionist-facts";
    this.history = doc.createElement("ol");
    this.runs = doc.createElement("p");
    this.frame = doc.createElement("iframe");
    this.frame.title = "Toyota's expense and evidence browser";
    this.frame.style.cssText =
      "width:100%;height:520px;border:1px solid #888;background:white";
    this.frame.hidden = true;
    root.append(
      title,
      this.status,
      this.facts,
      this.runs,
      this.history,
      this.frame,
    );
  }
  show(state: WorkState): void {
    // The raw `status: message` line is kept verbatim: it is the assertion target of the
    // synthetic browser check and of the screen-reader announcement, and a reader who has
    // learned to watch it should keep seeing exactly what the server said.
    this.status.textContent = `${state.status}: ${state.message}`;
    this.describe(this.presenter.present(state));
    this.history.replaceChildren(
      ...state.history.slice(-6).map((text) => {
        const item = this.doc.createElement("li");
        item.textContent = text;
        return item;
      }),
    );
    this.runs.replaceChildren();
    const id = state.run_ids.at(-1);
    if (id && /^[a-f0-9]{8}$/.test(id)) {
      const link = this.doc.createElement("a");
      link.textContent = `Latest ADW run: ${id}`;
      // Same-origin viewer proxy; a phone must never follow localhost:4600.
      link.href = `/receptionist_training.html?trace=${id}`;
      link.target = "_blank";
      this.runs.append(link);
    }
  }
  /** Each row is labelled, so no condition can be mistaken for another by skimming. */
  private describe(facts: WorkFacts): void {
    this.facts.dataset.phase = facts.phase;
    this.facts.dataset.verified = String(facts.verified);
    const rows: [string, string][] = [
      ["Right now", facts.headline],
      ["Assignment", facts.assignment],
      ["Record", facts.expense],
      ["Requested operation", facts.operation],
      ["Waiting for you", facts.waitingFor],
      ["Problem", facts.problem],
      ["Verified evidence", facts.evidence],
      ["Operation and run", facts.identity],
    ];
    this.facts.replaceChildren(
      ...rows
        .filter(([, value]) => value)
        .flatMap(([label, value]) => {
          const term = this.doc.createElement("dt");
          term.textContent = label;
          const detail = this.doc.createElement("dd");
          detail.textContent = value;
          detail.dataset.field = label.toLowerCase().replace(/ /g, "-");
          return [term, detail];
        }),
    );
  }
  async execute(command: BrowserCommand): Promise<BrowserOutcome> {
    this.frame.hidden = false;
    if (command.action === "evidence") {
      await this.load(command.url, false, command.id);
      const section = this.frame.contentDocument
        ?.querySelector("body")
        ?.textContent?.trim();
      if (!section)
        throw new Error("The supporting page loaded without readable content.");
      this.status.textContent = `Inspected supporting information: ${section.slice(0, 700)}`;
      return { ok: true, error: "" };
    }
    await this.load(
      `/receptionist_training.html?expense_id=${command.expense_id}&operation_id=${command.id}`,
      true,
      command.id,
    );
    return new Promise((resolve, reject) => {
      const view = this.doc.defaultView!;
      const timeout = view.setTimeout(() => {
        cleanup();
        reject(
          new Error(
            "The editor did not acknowledge its operation. Check the saved value before retrying.",
          ),
        );
      }, 30000);
      const cleanup = () => {
        view.clearTimeout(timeout);
        view.removeEventListener("message", receive);
      };
      const receive = (event: MessageEvent) => {
        if (
          event.source !== this.frame.contentWindow ||
          event.origin !== view.location.origin ||
          event.data?.channel !== "toyota-editor-result" ||
          event.data?.id !== command.id
        )
          return;
        cleanup();
        resolve({
          ok: event.data.ok === true,
          error: typeof event.data.error === "string" ? event.data.error : "",
        });
      };
      view.addEventListener("message", receive);
      this.frame.contentWindow!.postMessage(
        { channel: "toyota-editor-command", command },
        view.location.origin,
      );
    });
  }
  private load(
    url: string,
    editor: boolean,
    operationId: string,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const view = this.doc.defaultView!;
      const timeout = view.setTimeout(() => {
        cleanup();
        reject(new Error("The browser page did not become ready."));
      }, 30000);
      const cleanup = () => {
        view.clearTimeout(timeout);
        view.removeEventListener("message", ready);
        this.frame.removeEventListener("load", loaded);
      };
      const ready = (event: MessageEvent) => {
        if (
          event.source === this.frame.contentWindow &&
          event.origin === view.location.origin &&
          event.data?.channel === "toyota-editor-ready" &&
          event.data?.operation_id === operationId
        ) {
          cleanup();
          resolve();
        }
      };
      const loaded = () => {
        if (!editor) {
          cleanup();
          resolve();
        }
      };
      view.addEventListener("message", ready);
      this.frame.addEventListener("load", loaded);
      this.frame.src = url;
    });
  }
}
