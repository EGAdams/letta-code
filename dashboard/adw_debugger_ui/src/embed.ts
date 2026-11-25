// Composition root for one ADW run's sequence diagram inside another page
// (the object debugger on :8790). The page hands over a host element and the
// URL of a one-run feed; the module brings Vue with it.
import { type App, createApp } from "vue";
import { DebuggerController } from "./controller";
import { FixedRunPolicy } from "./domain/run-selection";
import { ProgressTimeoutStallPolicy } from "./domain/stall-policy";
import { FetchJson, ServerAlignedClock, WindowTimer } from "./infra/browser";
import { NoLegacyTerminal, NothingCleared } from "./infra/embedded";
import { PollingEventSource } from "./infra/polling-event-source";
import { LastGoodDiagramRenderer } from "./infra/safe-renderer";
import RunSequencePanel from "./ui/RunSequencePanel.vue";

export interface RunSequenceOptions {
  /** One-run feed, e.g. /api/adw-sequence?run=<adw_id>. `after=` is appended. */
  url: string;
  runId: string;
}

export interface MountedRunSequence {
  controller: DebuggerController;
  unmount(): void;
}

export function mountRunSequence(
  host: Element,
  options: RunSequenceOptions,
): MountedRunSequence {
  const timer = new WindowTimer();
  let running = true;
  const controller = new DebuggerController({
    source: new PollingEventSource(new FetchJson(), timer, {
      url: options.url,
      activeMs: 1500,
      idleMs: 15000,
      retryStepMs: 2000,
      retryMaxMs: 15000,
      isActive: () => running && document.visibilityState !== "hidden",
    }),
    selection: new FixedRunPolicy(options.runId),
    stall: new ProgressTimeoutStallPolicy(),
    renderer: new LastGoodDiagramRenderer(),
    cleared: new NothingCleared(),
    legacy: new NoLegacyTerminal(),
    clock: new ServerAlignedClock(),
    timer,
  });
  const stopWatching = controller.subscribe((view) => {
    running = view.runStatus === "running" || view.runStatus === null;
  });
  const app: App = createApp(RunSequencePanel, { controller });
  app.mount(host);
  controller.start();
  return {
    controller,
    unmount() {
      stopWatching();
      controller.dispose();
      app.unmount();
    },
  };
}
