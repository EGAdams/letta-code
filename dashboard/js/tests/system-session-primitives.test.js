import { describe, expect, test } from "bun:test";
import { Clock, IdSource } from "../abstract/session-clock.js";
import {
  RandomIdSource,
  SystemClock,
} from "../implementation/system-session-primitives.js";

describe("SystemClock", () => {
  test("reads the injected time source", () => {
    let t = 5;
    const clock = new SystemClock(() => t);
    expect(clock.now()).toBe(5);
    t = 9;
    expect(clock.now()).toBe(9);
    expect(clock).toBeInstanceOf(Clock);
  });

  test("defaults to Date.now", () => {
    const before = Date.now();
    const now = new SystemClock().now();
    expect(now).toBeGreaterThanOrEqual(before);
  });
});

describe("RandomIdSource", () => {
  test("prefixes the id so a generation is recognisable in a log", () => {
    const ids = new RandomIdSource({ randomUUID: () => "abc" });
    expect(ids.next("gen")).toBe("gen-abc");
    expect(ids).toBeInstanceOf(IdSource);
  });

  test("falls back to a counter where randomUUID is missing", () => {
    const ids = new RandomIdSource({});
    const first = ids.next("gen");
    const second = ids.next("gen");
    expect(first).not.toBe(second);
    expect(first.startsWith("gen-")).toBe(true);
  });

  test("survives an environment with no crypto at all", () => {
    const ids = new RandomIdSource(null);
    expect(() => ids.next()).not.toThrow();
  });
});
