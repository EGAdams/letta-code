import { expect, test } from "bun:test";
import { decodeCheckpoint, decodeRun } from "../src/evidence/decoders";
import { ReceptionistEvidenceSource } from "../src/evidence/receptionist-evidence";

const state = {
  assignment: "tax_issues",
  environment: "training",
  status: "ready",
  expense_id: 900001,
  category: "Walgreens (RM)",
  message: "Editor opened",
  command: null,
  run_ids: ["1234abcd"],
};
const event = (type: string, payload = {}, phase = "p1") => ({
  adw_id: "1234abcd",
  phase_id: phase,
  type,
  name: "load_assignment",
  ts: "2026-10-18T15:00:00Z",
  payload,
});

test("checkpoint decoder preserves pending work without treating ready as verified", () => {
  expect(decodeCheckpoint({ ok: true, state }).status).toBe("ready");
  expect(
    decodeCheckpoint({
      ok: true,
      state: { ...state, command: { action: "category" } },
    }).pending,
  ).toBe("category");
  expect(
    decodeCheckpoint({
      ok: true,
      state: { ...state, expense_id: null, run_ids: [] },
    }).expense,
  ).toBeNull();
});

test("invalid checkpoint shapes and unsafe run IDs fail closed", () => {
  for (const value of [
    null,
    {},
    { ok: false, state },
    { ok: true, state: { ...state, expense_id: "900001" } },
    { ok: true, state: { ...state, run_ids: ["../secret"] } },
    { ok: true, state: { ...state, command: {} } },
  ]) {
    expect(() => decodeCheckpoint(value)).toThrow();
  }
});

test("phase events produce ordered evidence, not inferred save success", () => {
  const result = decodeRun(
    {
      ok: true,
      run_id: "1234abcd",
      events: [
        event("phase_start", { description: "Restore the checkpoint" }),
        event("phase_end", { status: "success" }),
        event("phase_start", {}, "p2"),
      ],
    },
    "1234abcd",
  );
  expect(result.phases.map((phase) => phase.status)).toEqual([
    "Completed",
    "No completion recorded",
  ]);
  expect(result.phases[0].description).toBe("Restore the checkpoint");
});

test("failed, unknown and truncated phase records remain explicit", () => {
  const result = decodeRun(
    {
      ok: true,
      run_id: "1234abcd",
      events: [
        event("phase_end", { status: "error" }),
        event("phase_end", { status: "other" }, "p2"),
      ],
    },
    "1234abcd",
  );
  expect(result.phases[0].status).toBe("Failed");
  expect(result.phases[0].started).toBe("");
  expect(result.phases[1].status).toBe("Unknown result");
  expect(
    decodeRun(
      {
        ok: true,
        run_id: "1234abcd",
        events: Array.from({ length: 500 }, () => event("log")),
      },
      "1234abcd",
    ).limited,
  ).toBe(true);
});

test("cross-run and malformed trace data are rejected", () => {
  for (const value of [
    { ok: true, run_id: "deadbeef", events: [] },
    {
      ok: true,
      run_id: "1234abcd",
      events: [{ ...event("phase_start"), adw_id: "deadbeef" }],
    },
    { ok: true, run_id: "1234abcd", events: [null] },
  ]) {
    expect(() => decodeRun(value, "1234abcd")).toThrow();
  }
});

test("adapter only GETs existing routes with no cache and an abort signal", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const source = new ReceptionistEvidenceSource({
    get: async (url, init) => {
      calls.push({ url, init });
      return url.includes("/trace")
        ? { ok: true, run_id: "1234abcd", events: [] }
        : { ok: true, state };
    },
  });
  const signal = new AbortController().signal;
  await source.checkpoint(signal);
  await source.run("1234abcd", signal);
  expect(calls.map((call) => call.url)).toEqual([
    "/api/receptionist-work",
    "/api/receptionist-work/trace?run=1234abcd",
  ]);
  for (const call of calls) {
    expect(call.init.method).toBe("GET");
    expect(call.init.cache).toBe("no-store");
    expect(call.init.signal).toBe(signal);
  }
  await expect(source.run("../secret", signal)).rejects.toThrow();
  expect(calls).toHaveLength(2);
});
