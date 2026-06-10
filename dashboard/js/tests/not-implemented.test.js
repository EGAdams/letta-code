import { describe, expect, test } from "bun:test";
import {
  abstractMethod,
  NotImplementedError,
} from "../abstract/not-implemented.js";

describe("NotImplementedError", () => {
  test("abstractMethod throws NotImplementedError naming the method", () => {
    expect(() => abstractMethod("doThing")).toThrow(NotImplementedError);
    expect(() => abstractMethod("doThing")).toThrow(/doThing\(\) is abstract/);
  });

  test("error has the expected name for catch-by-name", () => {
    try {
      abstractMethod("x");
    } catch (e) {
      expect(e.name).toBe("NotImplementedError");
    }
  });
});
