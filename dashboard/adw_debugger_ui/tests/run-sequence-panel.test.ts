import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { DebuggerController } from "../src/controller";
import { FixedRunPolicy } from "../src/domain/run-selection";
import { ProgressTimeoutStallPolicy } from "../src/domain/stall-policy";
import { NoLegacyTerminal, NothingCleared } from "../src/infra/embedded";
import { PollingEventSource } from "../src/infra/polling-event-source";
import { LastGoodDiagramRenderer } from "../src/infra/safe-renderer";
import RunSequencePanel from "../src/ui/RunSequencePanel.vue";
import {
  constructed,
  FakeClock,
  FakeTimer,
  ManualSource,
  page,
  run,
  ScriptedHttp,
  started,
} from "./fixtures";

function embedded(runId: string) {
  const source = new ManualSource();
  const controller = new DebuggerController({
    source,
    clock: new FakeClock(),
    cleared: new NothingCleared(),
    legacy: new NoLegacyTerminal(),
    timer: new FakeTimer(),
    selection: new FixedRunPolicy(runId),
    stall: new ProgressTimeoutStallPolicy(),
    renderer: new LastGoodDiagramRenderer(),
  });
  controller.start();
  return { source, controller };
}

describe("one-run embed", () => {
  it("stays on the run it was given, even when a newer run appears", () => {
    const { source, controller } = embedded("r1");
    let runId: string | null = null;
    controller.subscribe((view) => {
      runId = view.runId;
    });
    source.push(
      page(
        [run("r1", "success"), run("r2", "running", 5)],
        [...constructed("r1", "a", "a"), ...constructed("r2", "a", "a", 5)],
        { bootstrap: true },
      ),
    );
    expect(runId).toBe("r1");
  });

  it("opens a phase's console on click, switches on another phase, closes on the same phase", async () => {
    const { source, controller } = embedded("r1");
    source.push(
      page(
        [run("r1")],
        [
          ...constructed("r1", "a", "a"),
          ...constructed("r1", "b", "b"),
          ...started("r1", "a", "a", 1),
          ...started("r1", "b", "b", 2),
        ],
        { bootstrap: true },
      ),
    );
    const wrapper = mount(RunSequencePanel, { props: { controller } });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-field="popup"]').exists()).toBe(false);
    const phase = (name: string) =>
      wrapper
        .findAll('.sd-titles-top [data-participant="phase"]')
        .find((b) => b.find(".sd-name").text() === name)!;

    await phase("a").trigger("click");
    const popup = () => wrapper.find('[data-field="popup"]');
    expect(popup().exists()).toBe(true);
    expect(popup().text()).toContain("> a");
    expect(popup().text()).not.toContain("> b");

    await phase("b").trigger("click");
    expect(popup().text()).toContain("> b");
    expect(popup().text()).not.toContain("> a");

    await phase("b").trigger("click");
    expect(popup().exists()).toBe(false);
    wrapper.unmount();
  });

  it("polls a feed url that already has a query with &after=", async () => {
    const http = new ScriptedHttp([
      page([run("r1")], constructed("r1", "a", "a"), { bootstrap: true }),
      page([run("r1")], []),
    ]);
    const timer = new FakeTimer();
    const feed = new PollingEventSource(http, timer, {
      url: "/api/adw-sequence?run=r1",
      activeMs: 500,
      idleMs: 5000,
      retryStepMs: 1000,
      retryMaxMs: 5000,
      isActive: () => true,
    });
    feed.subscribe({ onPage: () => {}, onConnection: () => {} });
    feed.start();
    await new Promise((resolve) => setTimeout(resolve, 0));
    timer.fire();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(http.urls[1]).toMatch(/^\/api\/adw-sequence\?run=r1&after=\d+$/);
    feed.stop();
  });
});
