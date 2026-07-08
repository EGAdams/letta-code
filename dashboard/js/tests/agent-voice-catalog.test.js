import { describe, expect, test } from "bun:test";
import {
  AgentVoiceCatalog,
  DEFAULT_AGENT_VOICE_PREFERENCES,
} from "../abstract/agent-voice-catalog.interface.js";

const VOICES = [
  { lang: "en-US", name: "Microsoft Zira" },
  { lang: "en-US", name: "Microsoft Aria" },
  { lang: "en-US", name: "Microsoft Jenny" },
  { lang: "en-US", name: "Microsoft Samantha" },
  { lang: "en-US", name: "Microsoft Salli" },
  { lang: "en-US", name: "Microsoft David" },
];

describe("AgentVoiceCatalog (Strategy/Registry)", () => {
  test("assigns each known agent its preferred voice", () => {
    const catalog = new AgentVoiceCatalog();
    expect(catalog.voiceFor("Scissari", VOICES).name).toBe("Microsoft Zira");
    expect(catalog.voiceFor("Mazda", VOICES).name).toBe("Microsoft Aria");
    expect(catalog.voiceFor("Frita", VOICES).name).toBe("Microsoft Jenny");
    expect(catalog.voiceFor("Hailey", VOICES).name).toBe("Microsoft Samantha");
    expect(catalog.voiceFor("Jeri", VOICES).name).toBe("Microsoft Salli");
  });

  test("caches the assignment so repeated lookups are stable", () => {
    const catalog = new AgentVoiceCatalog();
    const first = catalog.voiceFor("Scissari", VOICES);
    const second = catalog.voiceFor("Scissari", VOICES);
    expect(second).toBe(first);
  });

  test("never falls back to a male voice, reusing a female one instead", () => {
    const catalog = new AgentVoiceCatalog();
    // Claim every preferred voice first.
    for (const name of Object.keys(DEFAULT_AGENT_VOICE_PREFERENCES)) {
      catalog.voiceFor(name, VOICES);
    }
    const picked = catalog.voiceFor("SomeOtherAgent", VOICES);
    // Only "Microsoft David" (male) is left unclaimed among en-US voices, but
    // the male-avoidance rule (commit b18052fa) reuses a female voice instead.
    expect(picked.name).not.toBe("Microsoft David");
    expect(picked.name).toBe("Microsoft Zira");
  });

  test("assigns the extended roster (Mazda stages) its prefs", () => {
    const voices = [
      { lang: "en-US", name: "Microsoft Ana" },
      { lang: "en-US", name: "Microsoft Cora" },
      { lang: "en-US", name: "Microsoft Elizabeth" },
      { lang: "en-US", name: "Microsoft Sara" },
      { lang: "en-US", name: "Microsoft Nancy" },
    ];
    const catalog = new AgentVoiceCatalog();
    expect(catalog.voiceFor("Mazda Router", voices).name).toBe("Microsoft Ana");
    expect(catalog.voiceFor("Mazda Parser", voices).name).toBe(
      "Microsoft Cora",
    );
    expect(catalog.voiceFor("Mazda Vendor Identity", voices).name).toBe(
      "Microsoft Elizabeth",
    );
    expect(catalog.voiceFor("Mazda Receipt Linker", voices).name).toBe(
      "Microsoft Sara",
    );
    expect(catalog.voiceFor("Mazda Categorization", voices).name).toBe(
      "Microsoft Nancy",
    );
  });

  test("voiceFor returns the fallback when no voices are available", () => {
    const catalog = new AgentVoiceCatalog();
    const fallback = { lang: "en-US", name: "Fallback" };
    expect(catalog.voiceFor("Scissari", [], fallback)).toBe(fallback);
  });

  test("reset() clears cached assignments", () => {
    const catalog = new AgentVoiceCatalog();
    const before = catalog.voiceFor("Scissari", VOICES);
    catalog.reset();
    const after = catalog.voiceFor("Scissari", VOICES);
    expect(after).toEqual(before);
  });

  test("custom preferences can be injected", () => {
    const catalog = new AgentVoiceCatalog({ SomeAgent: [/david/i] });
    expect(catalog.voiceFor("SomeAgent", VOICES).name).toBe("Microsoft David");
  });
});
