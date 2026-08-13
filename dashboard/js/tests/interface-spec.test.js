import { describe, expect, test } from "bun:test";
import {
  STATUS_LABELS,
  Status,
  validateInterfaceSpec,
  validateSpecs,
} from "../plans/interface-spec.js";
import { voiceCommunicationSpecs } from "../plans/voice-communication/index.js";

const minimal = (overrides = {}) => ({
  id: "thing",
  name: "Thing",
  status: Status.PLANNED,
  responsibility: ["It does one job."],
  ...overrides,
});

describe("validateInterfaceSpec", () => {
  test("accepts a minimal well-formed spec", () => {
    expect(validateInterfaceSpec(minimal())).toBeTruthy();
  });

  test.each([
    ["a non-object", null, "must be an object"],
    ["a bad id", minimal({ id: "Not A Slug" }), "lowercase slug"],
    ["a missing name", minimal({ name: "" }), "name required"],
    ["an unknown status", minimal({ status: "almost" }), "status must be"],
    ["no responsibility", minimal({ responsibility: [] }), "responsibility"],
  ])("rejects %s", (_label, spec, message) => {
    expect(() => validateInterfaceSpec(spec)).toThrow(message);
  });

  test("rejects an implementation with an unknown kind", () => {
    expect(() =>
      validateInterfaceSpec(
        minimal({ implementations: [{ name: "X", kind: "maybe" }] }),
      ),
    ).toThrow("current/planned/deprecated");
  });

  test("rejects a diagram with no Mermaid code", () => {
    expect(() =>
      validateInterfaceSpec(minimal({ diagrams: [{ title: "X" }] })),
    ).toThrow("Mermaid code");
  });

  test("rejects a test entry that does not say what it proves", () => {
    expect(() =>
      validateInterfaceSpec(minimal({ tests: { files: [{ path: "a.js" }] } })),
    ).toThrow("what it proves");
  });

  test("rejects an off-origin link", () => {
    expect(() =>
      validateInterfaceSpec(
        minimal({ links: [{ label: "X", href: "https://example.com" }] }),
      ),
    ).toThrow("root-relative");
  });
});

describe("validateSpecs", () => {
  test("rejects duplicate ids", () => {
    expect(() => validateSpecs([minimal(), minimal()])).toThrow(
      "duplicate spec id",
    );
  });

  test("rejects an empty workspace", () => {
    expect(() => validateSpecs([])).toThrow("at least one");
  });
});

describe("the Voice Communication workspace data", () => {
  test("every spec is valid and uniquely identified", () => {
    expect(() => validateSpecs(voiceCommunicationSpecs)).not.toThrow();
  });

  test("opens on the Overview", () => {
    expect(voiceCommunicationSpecs[0].id).toBe("overview");
  });

  test("covers every interface the plan named", () => {
    const ids = voiceCommunicationSpecs.map((s) => s.id);
    for (const required of [
      "voice-session",
      "conversation-coordinator",
      "iconversationagent",
      "letta-agent-adapter",
      "detection-interface",
      "language-processor",
    ]) {
      expect(ids).toContain(required);
    }
  });

  test("every tab carries at least one diagram and some next work", () => {
    for (const spec of voiceCommunicationSpecs) {
      expect(spec.diagrams?.length ?? 0).toBeGreaterThan(0);
      expect(spec.nextWork?.length ?? 0).toBeGreaterThan(0);
    }
  });

  test("unbuilt interfaces are not dressed up as finished", () => {
    const byId = Object.fromEntries(
      voiceCommunicationSpecs.map((s) => [s.id, s]),
    );
    expect(byId["voice-session"].status).toBe(Status.PLANNED);
    expect(byId["iconversationagent"].status).toBe(Status.PLANNED);
    // A planned interface must not claim tests it does not have.
    expect(byId["voice-session"].tests.files).toEqual([]);
  });

  test("every status used has a human label", () => {
    for (const spec of voiceCommunicationSpecs)
      expect(STATUS_LABELS[spec.status]).toBeTruthy();
  });
});
