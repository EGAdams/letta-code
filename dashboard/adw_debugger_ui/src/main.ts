// Composition root for the Live ADW Sequence Debugger. The only file that names
// a concrete class. Loaded by its own <script type="module"> tag, the same way
// terminal-page.js is, and mounts directly above the existing #terminal-stream.
import { type App, createApp } from "vue";
import { DebuggerController } from "./controller";
import { EarliestActiveRunPolicy } from "./domain/run-selection";
import { ProgressTimeoutStallPolicy } from "./domain/stall-policy";
import {
  DomLegacyTerminal,
  FetchJson,
  LocalStorageClearStore,
  ServerAlignedClock,
  WindowTimer,
} from "./infra/browser";
import { PollingEventSource } from "./infra/polling-event-source";
import { LastGoodDiagramRenderer } from "./infra/safe-renderer";
import DebuggerPanel from "./ui/DebuggerPanel.vue";

export interface MountedDebugger {
  controller: DebuggerController;
  unmount(): void;
}

export function mountAdwDebugger(
  doc: Document = document,
): MountedDebugger | null {
  const view = doc.getElementById("terminal");
  const stream = doc.getElementById("terminal-stream");
  const toolbar = view?.querySelector(".terminal-toolbar") ?? stream;
  if (!view || !stream || !toolbar || doc.getElementById("adw-debugger-root"))
    return null;

  const host = doc.createElement("div");
  host.id = "adw-debugger-root";
  toolbar.parentNode!.insertBefore(host, toolbar);

  const timer = new WindowTimer();
  const controller = new DebuggerController({
    source: new PollingEventSource(new FetchJson(), timer, {
      url: "/api/adw-debugger/feed",
      activeMs: 500,
      idleMs: 5000,
      retryStepMs: 1000,
      retryMaxMs: 5000,
      isActive: () =>
        view.classList.contains("active") && doc.visibilityState !== "hidden",
    }),
    selection: new EarliestActiveRunPolicy(),
    stall: new ProgressTimeoutStallPolicy(),
    renderer: new LastGoodDiagramRenderer(),
    cleared: new LocalStorageClearStore(),
    legacy: new DomLegacyTerminal(stream),
    clock: new ServerAlignedClock(),
    timer,
  });
  const app: App = createApp(DebuggerPanel, { controller });
  app.mount(host);
  controller.start();

  // Out of sight the feed is read every 5 s; the moment the tab is opened, read it now.
  const wake = () => controller.wake();
  const watcher = new MutationObserver(wake);
  watcher.observe(view, { attributes: true, attributeFilter: ["class"] });
  doc.addEventListener("visibilitychange", wake);
  return {
    controller,
    unmount() {
      watcher.disconnect();
      doc.removeEventListener("visibilitychange", wake);
      controller.dispose();
      app.unmount();
      host.remove();
    },
  };
}

(window as unknown as { adwDebugger?: MountedDebugger | null }).adwDebugger =
  mountAdwDebugger();
