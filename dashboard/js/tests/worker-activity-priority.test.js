import { describe, expect, test } from "bun:test";
import {
  isStalledTask,
  rankActiveTasks,
} from "../abstract/worker-activity-priority.js";

describe("Worker Activity top-five priority ranking", () => {
  test("flags zero-attempt queued work as stalled, and nothing else", () => {
    expect(isStalledTask({ status: "queued", attempts: 0 })).toBe(true);
    expect(isStalledTask({ status: "queued", attempts: 2 })).toBe(false);
    expect(isStalledTask({ status: "running", attempts: 0 })).toBe(false);
    expect(isStalledTask({ status: "failed", attempts: 0 })).toBe(false);
  });

  test("orders failed/stalled first, then running by recency, then queued by age, then recent results", () => {
    const tasks = [
      {
        id: "completed-1",
        status: "succeeded",
        last_update: "2026-11-05T09:00:00Z",
      },
      {
        id: "queued-old",
        status: "queued",
        attempts: 2,
        last_update: "2026-11-05T06:00:00Z",
      },
      {
        id: "queued-new",
        status: "queued",
        attempts: 1,
        last_update: "2026-11-05T08:00:00Z",
      },
      {
        id: "running-old",
        status: "running",
        last_update: "2026-11-05T07:00:00Z",
      },
      {
        id: "running-new",
        status: "running",
        last_update: "2026-11-05T09:30:00Z",
      },
      {
        id: "stalled",
        status: "queued",
        attempts: 0,
        last_update: "2026-11-05T05:00:00Z",
      },
      { id: "failed-1", status: "failed", last_update: "2026-11-05T04:00:00Z" },
    ];
    const ranked = rankActiveTasks(tasks, 5);
    expect(ranked.map((t) => t.id)).toEqual([
      "failed-1",
      "stalled",
      "running-new",
      "running-old",
      "queued-old",
    ]);
  });

  test("fills remaining slots with recent results only when there is room", () => {
    const tasks = [
      { id: "r1", status: "running", last_update: "2026-11-05T09:00:00Z" },
      {
        id: "done-old",
        status: "succeeded",
        last_update: "2026-11-05T01:00:00Z",
      },
      {
        id: "done-new",
        status: "succeeded",
        last_update: "2026-11-05T08:00:00Z",
      },
    ];
    const ranked = rankActiveTasks(tasks, 5);
    expect(ranked.map((t) => t.id)).toEqual(["r1", "done-new", "done-old"]);
  });

  test("breaks ties on task id so the order is stable across calls", () => {
    const tasks = [
      { id: "b", status: "running", last_update: "2026-11-05T09:00:00Z" },
      { id: "a", status: "running", last_update: "2026-11-05T09:00:00Z" },
    ];
    expect(rankActiveTasks(tasks).map((t) => t.id)).toEqual(["a", "b"]);
    expect(rankActiveTasks(tasks).map((t) => t.id)).toEqual(["a", "b"]);
  });

  test("never fabricates a row: a duplicate id collapses to one, and output never exceeds the real task count", () => {
    const tasks = [
      {
        id: "dup",
        status: "running",
        agent: "first",
        last_update: "2026-11-05T09:00:00Z",
      },
      {
        id: "dup",
        status: "running",
        agent: "second",
        last_update: "2026-11-05T09:30:00Z",
      },
    ];
    const ranked = rankActiveTasks(tasks, 5);
    expect(ranked).toHaveLength(1);
    expect(ranked[0].agent).toBe("first");
    expect(rankActiveTasks([], 5)).toHaveLength(0);
    expect(
      rankActiveTasks([{ id: "only", status: "running" }], 5),
    ).toHaveLength(1);
  });

  test("respects the limit even with more real tasks available", () => {
    const tasks = Array.from({ length: 8 }, (_, i) => ({
      id: `t${i}`,
      status: "queued",
      attempts: 1,
      last_update: "2026-11-05T09:00:00Z",
    }));
    expect(rankActiveTasks(tasks, 5)).toHaveLength(5);
  });
});
