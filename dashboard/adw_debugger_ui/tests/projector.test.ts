import { describe, expect, it } from "vitest";
import { project } from "../src/domain/projector";
import { type DebuggerState, emptyState } from "../src/domain/state";
import { constructed, ended, ev, page, run, started } from "./fixtures";

function feed(
  state: DebuggerState,
  runId: string,
  events: ReturnType<typeof ev>[],
  status: "running" | "success" | "fail" = "running",
) {
  return project(state, page([run(runId, status)], events));
}

const names = (state: DebuggerState, runId: string) =>
  state.runs[runId].visible;

describe("projector", () => {
  it("shows constructed instances as waiting columns before anything runs", () => {
    const state = feed(emptyState(), "r1", [
      ...constructed("r1", "prepare", "prepare"),
      ...constructed("r1", "report", "report"),
    ]);
    expect(names(state, "r1")).toEqual(["r1:prepare", "r1:report"]);
    expect(state.runs.r1.phases["r1:prepare"]).toMatchObject({
      constructed: true,
      started: false,
      purpose: "purpose of prepare",
    });
  });

  it("folds the phase id stand-in into its constructed instance when bound arrives", () => {
    let state = feed(
      emptyState(),
      "r1",
      constructed("r1", "prepare", "prepare"),
    );
    state = feed(state, "r1", started("r1", "prepare", "prepare", 1));
    expect(Object.keys(state.runs.r1.phases)).toEqual(["r1:prepare"]);
    expect(state.runs.r1.phases["r1:prepare"]).toMatchObject({
      started: true,
      phaseId: "r1_01_prepare",
    });
    expect(state.runs.r1.instanceOfPhase).toEqual({
      r1_01_prepare: "r1:prepare",
    });
  });

  it("keeps a finished column until the next phase starts, then replaces it", () => {
    let state = feed(emptyState(), "r1", [
      ...constructed("r1", "a", "a"),
      ...constructed("r1", "b", "b"),
      ...started("r1", "a", "a", 1),
    ]);
    state = feed(state, "r1", ended("r1", "a", "a", 1, "pass"));
    expect(names(state, "r1")).toEqual(["r1:a", "r1:b"]);
    expect(state.runs.r1.phases["r1:a"].outcome).toBe("pass");
    state = feed(state, "r1", started("r1", "b", "b", 2));
    expect(names(state, "r1")).toEqual(["r1:b"]);
  });

  it("retains the last diagram when nothing is active any more", () => {
    let state = feed(emptyState(), "r1", [
      ...constructed("r1", "a", "a"),
      ...started("r1", "a", "a", 1),
    ]);
    state = feed(state, "r1", ended("r1", "a", "a", 1, "pass"), "success");
    expect(names(state, "r1")).toEqual(["r1:a"]);
  });

  it("keeps the failed phase and the instances that never ran on a failed run", () => {
    let state = feed(emptyState(), "r1", [
      ...constructed("r1", "a", "a"),
      ...constructed("r1", "b", "b"),
      ...started("r1", "a", "a", 1),
    ]);
    state = feed(state, "r1", ended("r1", "a", "a", 1, "fail"));
    state = feed(
      state,
      "r1",
      [
        ev("r1", "cleanup", {
          instance_id: "r1:b",
          phase_name: "b",
          message: "cleanup ok -- never executed",
        }),
      ],
      "fail",
    );
    expect(names(state, "r1")).toEqual(["r1:a", "r1:b"]);
    expect(state.runs.r1.phases["r1:a"].outcome).toBe("fail");
    expect(state.runs.r1.phases["r1:b"]).toMatchObject({
      abandoned: true,
      outcome: null,
    });
  });

  it("never lets cleanup or a late event change a recorded outcome", () => {
    let state = feed(emptyState(), "r1", [
      ...constructed("r1", "a", "a"),
      ...started("r1", "a", "a", 1),
      ...ended("r1", "a", "a", 1, "fail"),
    ]);
    state = feed(state, "r1", [
      ev("r1", "progress", {
        phase_id: "r1_01_a",
        instance_id: "r1:a",
        message: "late",
      }),
      ev("r1", "cleanup", {
        phase_id: "r1_01_a",
        instance_id: "r1:a",
        message: "cleanup ok",
      }),
      ev("r1", "phase_end", {
        phase_id: "r1_01_a",
        instance_id: "r1_01_a",
        status: "pass",
      }),
    ]);
    expect(state.runs.r1.phases["r1:a"].outcome).toBe("fail");
  });

  it("drops duplicate events and returns the same state object when a page adds nothing", () => {
    const events = [
      ...constructed("r1", "a", "a"),
      ...started("r1", "a", "a", 1),
    ];
    const once = feed(emptyState(), "r1", events);
    const twice = feed(once, "r1", events);
    expect(twice).toBe(once);
    expect(once.logs).toHaveLength(events.length);
  });

  it("orders delayed events by cursor, not by arrival", () => {
    const events = [
      ...constructed("r1", "a", "a"),
      ...started("r1", "a", "a", 1),
    ];
    const state = feed(
      feed(emptyState(), "r1", events.slice(3)),
      "r1",
      events.slice(0, 3),
    );
    expect(state.logs.map((line) => line.cursor)).toEqual(
      events.map((event) => event.cursor),
    );
  });

  it("keeps two instances of the same phase name apart, and their tool calls with them", () => {
    let state = feed(emptyState(), "r1", [
      ...constructed("r1", "lookup-1", "lookup"),
      ...constructed("r1", "lookup-2", "lookup"),
      ...started("r1", "lookup-1", "lookup", 1),
    ]);
    state = feed(state, "r1", [
      ev("r1", "tool_call", {
        phase_id: "r1_01_lookup",
        instance_id: "r1:lookup-1",
        tool: "catalog.get",
        call_id: "c1",
        message: "catalog.get [c1]",
      }),
      ev("r1", "tool_result", {
        phase_id: "r1_01_lookup",
        instance_id: "r1:lookup-1",
        tool: "catalog.get",
        call_id: "c1",
        message: "catalog.get [c1] returned\nalpha",
      }),
    ]);
    expect(Object.keys(state.runs.r1.phases)).toEqual([
      "r1:lookup-1",
      "r1:lookup-2",
    ]);
    expect(state.runs.r1.arrows.map((a) => [a.from, a.to, a.dashed])).toEqual([
      ["r1:lookup-1", "r1:lookup-1", false],
      ["r1:lookup-1", "r1:lookup-1", true],
    ]);
  });

  it("draws a cross-phase arrow only from recorded source and target", () => {
    const state = feed(emptyState(), "r1", [
      ...constructed("r1", "a", "a"),
      ...constructed("r1", "b", "b"),
      ...started("r1", "a", "a", 1),
      ev("r1", "message", {
        phase_id: "r1_01_a",
        instance_id: "r1:a",
        source_instance: "r1:a",
        target_instance: "r1:b",
        message: "hi",
      }),
      ev("r1", "message", {
        phase_id: "r1_01_a",
        instance_id: "r1:a",
        message: "no target recorded",
      }),
    ]);
    expect(state.runs.r1.arrows.map((a) => [a.from, a.to])).toEqual([
      ["r1:a", "r1:b"],
      ["r1:a", "r1:a"],
    ]);
  });

  it("keeps simultaneous runs separate", () => {
    let state = project(
      emptyState(),
      page(
        [run("r1"), run("r2")],
        [...constructed("r1", "a", "a"), ...constructed("r2", "a", "a")],
      ),
    );
    state = project(
      state,
      page([run("r1"), run("r2")], started("r2", "a", "a", 1)),
    );
    expect(state.runs.r1.phases["r1:a"].started).toBe(false);
    expect(state.runs.r2.phases["r2:a"].started).toBe(true);
  });

  it("shows an ADW that is not instrumented by its phase ids", () => {
    const state = feed(emptyState(), "r9", [
      ev("r9", "phase_start", {
        phase_id: "r9_01_hello",
        phase_name: "hello",
        instance_id: "r9_01_hello",
        status: "running",
      }),
    ]);
    expect(names(state, "r9")).toEqual(["r9_01_hello"]);
  });
});
