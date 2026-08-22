import { describe, expect, test } from "bun:test";
import {
  AUTO_MODEL_HANDLE,
  isFreeTierModelHandle,
  providerPrefixOfHandle,
  quotaFallbackDisallowedPrefixes,
  selectDefaultAgentModel,
} from "../../agent/serverModelSelection";

// Incident 2026-07-04: on a self-hosted server the quota fallback picked
// letta/letta-free (first non-auto handle in the server list), which was
// backed by a stale OPENAI_API_KEY — every request died with an OpenAI 401
// UNAUTHENTICATED instead of continuing on a working provider.
describe("quota fallback model selection", () => {
  test("skips letta/letta-free when another provider handle is available", () => {
    const result = selectDefaultAgentModel({
      preferredModel: AUTO_MODEL_HANDLE,
      isSelfHosted: true,
      availableHandles: ["letta/letta-free", "chatgpt-plus-pro/gpt-5.4"],
      disallowedHandles: ["chatgpt-plus-pro/gpt-5.4"],
    });

    expect(result).toBe("chatgpt-plus-pro/gpt-5.4");
  });

  test("skips letta/letta-free even when it is listed before several real handles", () => {
    const result = selectDefaultAgentModel({
      isSelfHosted: true,
      availableHandles: [
        "letta/auto",
        "letta/letta-free",
        "anthropic/claude-haiku-4-5",
        "openai/gpt-5.4",
      ],
    });

    expect(result).toBe("anthropic/claude-haiku-4-5");
  });

  test("still uses letta/letta-free as the last resort when nothing else exists", () => {
    const result = selectDefaultAgentModel({
      isSelfHosted: true,
      availableHandles: ["letta/auto", "letta/letta-free"],
    });

    expect(result).toBe("letta/letta-free");
  });

  test("never selects a disallowed handle even as a free-tier last resort", () => {
    const result = selectDefaultAgentModel({
      isSelfHosted: true,
      availableHandles: ["letta/letta-free"],
      disallowedHandles: ["letta/letta-free"],
    });

    expect(result).toBeUndefined();
  });

  // Incident 2026-08-02: the self-hosted server exposed a base google_ai/* set
  // backed by a dead GEMINI_API_KEY alongside the working BYOK lc-gemini/* set.
  // The quota fallback picked google_ai/gemini-2.0-flash (first non-auto handle)
  // and every request died with API_KEY_INVALID. The working key lives on the
  // lc-gemini BYOK provider, so google_ai/ must be prefix-blocked on this server.
  test("skips handles matching a disallowed prefix (dead base provider key)", () => {
    const result = selectDefaultAgentModel({
      preferredModel: AUTO_MODEL_HANDLE,
      isSelfHosted: true,
      availableHandles: [
        "google_ai/gemini-2.0-flash",
        "lc-gemini/gemini-2.0-flash",
      ],
      disallowedHandlePrefixes: ["google_ai/"],
    });

    expect(result).toBe("lc-gemini/gemini-2.0-flash");
  });

  test("never selects a prefix-blocked handle even as the only real handle", () => {
    const result = selectDefaultAgentModel({
      preferredModel: AUTO_MODEL_HANDLE,
      isSelfHosted: true,
      availableHandles: ["google_ai/gemini-2.0-flash", "letta/letta-free"],
      disallowedHandlePrefixes: ["google_ai/"],
    });

    // google_ai/* is dead; letta/letta-free is the last-resort survivor.
    expect(result).toBe("letta/letta-free");
  });

  test("identifies free-tier handles", () => {
    expect(isFreeTierModelHandle("letta/letta-free")).toBe(true);
    expect(isFreeTierModelHandle("chatgpt-plus-pro/gpt-5.4")).toBe(false);
    expect(isFreeTierModelHandle(undefined)).toBe(false);
  });
});

// The quota-fallback prefix policy used to live inline in App.tsx (untestable
// inside a 6000-line React component). It is now a pure function.
describe("quotaFallbackDisallowedPrefixes", () => {
  test("providerPrefixOfHandle extracts the provider segment", () => {
    expect(providerPrefixOfHandle("chatgpt-plus-pro/gpt-5.4")).toBe(
      "chatgpt-plus-pro/",
    );
    expect(providerPrefixOfHandle("lc-gemini/gemini-2.0-flash")).toBe(
      "lc-gemini/",
    );
    expect(providerPrefixOfHandle("no-slash")).toBeUndefined();
    expect(providerPrefixOfHandle("/leading")).toBeUndefined();
    expect(providerPrefixOfHandle(undefined)).toBeUndefined();
    expect(providerPrefixOfHandle(null)).toBeUndefined();
  });

  test("blocks the current provider so quota fallback escapes to another one", () => {
    // Quota is account-scoped: falling back to a sibling model on the same
    // provider would just re-hit the limit.
    expect(
      quotaFallbackDisallowedPrefixes({
        currentModelLabel: "chatgpt-plus-pro/gpt-5.4",
      }),
    ).toEqual(["chatgpt-plus-pro/"]);
  });

  test("merges configured dead-provider prefixes with the current provider", () => {
    expect(
      quotaFallbackDisallowedPrefixes({
        currentModelLabel: "chatgpt-plus-pro/gpt-5.4",
        configuredDisabledPrefixes: ["google_ai/"],
      }),
    ).toEqual(["google_ai/", "chatgpt-plus-pro/"]);
  });

  test("dedups when the current provider is also configured-disabled", () => {
    expect(
      quotaFallbackDisallowedPrefixes({
        currentModelLabel: "google_ai/gemini-2.0-flash",
        configuredDisabledPrefixes: ["google_ai/"],
      }),
    ).toEqual(["google_ai/"]);
  });

  test("handles a missing/blank current model and empty config", () => {
    expect(quotaFallbackDisallowedPrefixes({})).toEqual([]);
    expect(
      quotaFallbackDisallowedPrefixes({ currentModelLabel: undefined }),
    ).toEqual([]);
  });
});
