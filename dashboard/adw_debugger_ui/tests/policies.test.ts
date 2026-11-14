import { describe, expect, it } from "vitest";
import type { RunSummary } from "../src/contracts";
import { clearRun, linesFor } from "../src/domain/log-selection";
import { project } from "../src/domain/projector";
import { EarliestActiveRunPolicy } from "../src/domain/run-selection";
import { ProgressTimeoutStallPolicy } from "../src/domain/stall-policy";
import { emptyState } from "../src/domain/state";
import {
  constructed,
  ended,
  MemoryClearStore,
  page,
  run,
  started,
  T0,
} from "./fixtures";

const summary = (
  runId: string,
  status: RunSummary["status"],
  startedAt: string,
): RunSummary => ({ runId, status, startedAt });
const none = { runId: null, pinReleased: false };

describe("run selection", () => {
  const policy = new EarliestActiveRunPolicy();

  it("follows the earliest-started running run, run id breaking a tie", () => {
    const runs = [
      summary("b", "running", "10:00"),
      summary("a", "running", "10:00"),
      summary("c", "running", "09:59"),
    ];
    expect(policy.select(none, runs).runId).toBe("c");
    expect(policy.select(none, runs.slice(0, 2)).runId).toBe("a");
  });

  it("does not let a second running run steal the view", () => {
    const runs = [
      summary("late", "running", "10:05"),
      summary("early", "running", "10:00"),
    ];
    expect(
      policy.select({ runId: "late", pinReleased: false }, runs).runId,
    ).toBe("late");
  });

  it("keeps a successful run until another run is active, then moves", () => {
    const current = { runId: "done", pinReleased: false };
    expect(
      policy.select(current, [summary("done", "success", "10:00")]),
    ).toEqual(current);
    expect(policy.mode(current, [summary("done", "success", "10:00")])).toBe(
      "completed",
    );
    expect(
      policy.select(current, [
        summary("done", "success", "10:00"),
        summary("next", "running", "10:01"),
      ]).runId,
    ).toBe("next");
  });

  it("moves to a run that started and finished between two reads, and pins it if it failed", () => {
    const current = { runId: "done", pinReleased: false };
    const runs = [
      summary("done", "success", "10:00"),
      summary("quick", "fail", "10:01"),
    ];
    const next = policy.select(current, runs);
    expect(next).toEqual({ runId: "quick", pinReleased: false });
    expect(policy.mode(next, runs)).toBe("pinned");
    expect(
      policy.select(current, [
        summary("older", "fail", "09:00"),
        summary("done", "success", "10:00"),
      ]),
    ).toEqual(current);
  });

  it("pins a failed or interrupted run until Follow live", () => {
    for (const status of ["fail", "interrupted"] as const) {
      const runs = [
        summary("bad", status, "10:00"),
        summary("next", "running", "10:01"),
      ];
      const pinned = policy.select({ runId: "bad", pinReleased: false }, runs);
      expect(pinned.runId).toBe("bad");
      expect(policy.mode(pinned, runs)).toBe("pinned");
      expect(policy.followLive(pinned, runs)).toEqual({
        runId: "next",
        pinReleased: false,
      });
    }
  });

  it("releases a pin with nothing running, and picks up the next run when it starts", () => {
    const released = policy.followLive({ runId: "bad", pinReleased: false }, [
      summary("bad", "fail", "10:00"),
    ]);
    expect(released).toEqual({ runId: "bad", pinReleased: true });
    expect(policy.mode(released, [summary("bad", "fail", "10:00")])).toBe(
      "completed",
    );
    expect(
      policy.select(released, [
        summary("bad", "fail", "10:00"),
        summary("next", "running", "10:02"),
      ]).runId,
    ).toBe("next");
  });

  it("shows the latest finished run on attach, and is idle with none", () => {
    expect(
      policy.select(none, [
        summary("old", "success", "09:00"),
        summary("new", "success", "10:00"),
      ]).runId,
    ).toBe("new");
    expect(policy.mode(none, [])).toBe("idle");
  });
});

describe("stall policy", () => {
  const policy = new ProgressTimeoutStallPolicy();
  const phase = {
    started: true,
    terminal: false,
    lastProgressAt: T0,
    waitDeadlineAt: null,
    waitReason: "",
  };

  it("is quiet until the timeout has fully elapsed", () => {
    expect(policy.evaluate(phase, T0 + 120_000, 120_000)).toBeNull();
    expect(policy.evaluate(phase, T0 + 121_000, 120_000)?.reason).toBe(
      "no progress for 121s (timeout 120s)",
    );
  });

  it("recovers when progress is recorded", () => {
    expect(
      policy.evaluate(
        { ...phase, lastProgressAt: T0 + 121_000 },
        T0 + 122_000,
        120_000,
      ),
    ).toBeNull();
  });

  it("judges an explicit wait by its own deadline, not the progress timeout", () => {
    const waiting = {
      ...phase,
      waitDeadlineAt: T0 + 300_000,
      waitReason: "gate",
    };
    expect(policy.evaluate(waiting, T0 + 200_000, 120_000)).toBeNull();
    expect(policy.evaluate(waiting, T0 + 305_000, 120_000)?.reason).toBe(
      "wait deadline passed 5s ago: gate",
    );
  });

  it("never stalls a phase that has not started or has finished", () => {
    expect(
      policy.evaluate({ ...phase, started: false }, T0 + 999_000, 1000),
    ).toBeNull();
    expect(
      policy.evaluate({ ...phase, terminal: true }, T0 + 999_000, 1000),
    ).toBeNull();
  });
});

describe("log selection and clear", () => {
  const both = [run("r1"), run("r2")];
  const state = project(
    emptyState(),
    page(both, [
      ...constructed("r1", "a", "a"),
      ...started("r1", "a", "a", 1),
      ...ended("r1", "a", "a", 1, "pass"),
      ...constructed("r1", "b", "b"),
      ...constructed("r2", "a", "a"),
    ]),
  );

  it("filters to one instance, including lines recorded under its phase id", () => {
    const lines = linesFor(
      state,
      { mode: "phase", runId: "r1", instanceId: "r1:a" },
      new MemoryClearStore(),
    );
    expect(lines.map((line) => line.kind)).toEqual([
      "constructed",
      "purpose",
      "phase_start",
      "console",
      "bound",
      "cleanup",
      "phase_end",
    ]);
  });

  it("clears one run only, and newer events still appear", () => {
    const cleared = new MemoryClearStore();
    clearRun(state, "r1", cleared);
    expect(
      linesFor(state, { mode: "all" }, cleared).every(
        (line) => line.runId === "r2",
      ),
    ).toBe(true);
    expect(
      linesFor(
        state,
        { mode: "phase", runId: "r1", instanceId: "r1:a" },
        cleared,
      ),
    ).toEqual([]);
    const later = project(state, page(both, started("r1", "b", "b", 2)));
    expect(
      linesFor(later, { mode: "all" }, cleared)
        .filter((line) => line.runId === "r1")
        .map((line) => line.kind),
    ).toEqual(["phase_start", "console", "bound"]);
  });

  it("does not bring cleared lines back when the same events are delivered again", () => {
    const cleared = new MemoryClearStore();
    clearRun(state, "r1", cleared);
    const replayed = project(
      emptyState(),
      page(
        both,
        state.logs.map((line) => ({
          cursor: line.cursor,
          event_id: line.eventId,
          recorded_at: line.recordedAt,
          kind: line.kind,
          message: "",
          machine: "",
          adw_name: "",
          run_id: line.runId,
          phase_id: line.phaseId,
          phase_name: "",
          instance_id: line.instanceId,
          attempt: null,
          status: null,
          source_instance: "",
          target_instance: "",
          tool: "",
          call_id: "",
          deadline_at: null,
        })),
      ),
    );
    expect(
      linesFor(replayed, { mode: "all" }, cleared).some(
        (line) => line.runId === "r1",
      ),
    ).toBe(false);
    expect(replayed.logs.length).toBe(state.logs.length);
  });
});
