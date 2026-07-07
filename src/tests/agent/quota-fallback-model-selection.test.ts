import { describe, expect, test } from "bun:test";
import {
  AUTO_MODEL_HANDLE,
  isFreeTierModelHandle,
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
      availableHandles: ["letta/letta-free", "chatgpt-plus-pro/gpt-5.4-mini"],
      disallowedHandles: ["chatgpt-plus-pro/gpt-5.4"],
    });

    expect(result).toBe("chatgpt-plus-pro/gpt-5.4-mini");
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

  test("identifies free-tier handles", () => {
    expect(isFreeTierModelHandle("letta/letta-free")).toBe(true);
    expect(isFreeTierModelHandle("chatgpt-plus-pro/gpt-5.4")).toBe(false);
    expect(isFreeTierModelHandle(undefined)).toBe(false);
  });
});
