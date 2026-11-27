import { describe, expect, test } from "bun:test";
import {
  identifiers,
  matches,
  stamp,
  terminalLine,
} from "../implementation/dom-live-activity.js";

const event = {
  at: "2026-11-27T18:00:00.123Z",
  machine: "R46",
  agent: "live-probe",
  state: "blocked",
  message: "failed — BLOCKED: dirty",
  task_id: "20261127T1",
  adw_id: "abcd1234",
};

describe("live activity lines", () => {
  test("show machine, agent, state, ms timestamp and ids", () => {
    expect(terminalLine(event)).toContain("R46/live-probe [BLOCKED] failed");
    expect(stamp(event.at)).toMatch(/\.123$/);
    expect(identifiers(event)).toBe("task 20261127T1 · adw abcd1234");
    expect(stamp("")).toBe("—");
  });

  test("filter by machine, agent and any identifier", () => {
    expect(matches(event, { machine: "SQMC" })).toBe(false);
    expect(matches(event, { agent: "live-probe", text: "ABCD1234" })).toBe(
      true,
    );
    expect(matches(event, { text: "t_missing" })).toBe(false);
  });
});
