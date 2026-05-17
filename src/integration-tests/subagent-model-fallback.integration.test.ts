import { describe, expect, test } from "bun:test";
import type { SubagentConfig } from "../agent/subagents";
import {
  buildSubagentArgs,
  isSubagentModelUnavailableError,
  resolveSubagentModel,
} from "../agent/subagents/manager";

const exploreConfig: SubagentConfig = {
  name: "explore",
  description: "Read-only explorer",
  systemPrompt: "Inspect the repository and report findings.",
  allowedTools: "all",
  recommendedModel: "auto",
  skills: [],
  memoryBlocks: "none",
  mode: "stateful",
  fork: false,
  background: false,
};

describe("subagent model fallback integration", () => {
  test("Task-style explore launch inherits parent model when server model list is empty", async () => {
    const model = await resolveSubagentModel({
      recommendedModel: exploreConfig.recommendedModel,
      parentModelHandle: "chatgpt-plus-pro/gpt-5.4-mini",
      availableHandles: new Set(),
    });

    const args = buildSubagentArgs(
      "explore",
      exploreConfig,
      model,
      "Find the messaging agent.",
    );

    expect(model).toBe("chatgpt-plus-pro/gpt-5.4-mini");
    expect(args).toContain("--new-agent");
    expect(args).toContain("--model");
    expect(args).toContain("chatgpt-plus-pro/gpt-5.4-mini");
    expect(args).not.toContain("letta/auto");
  });

  test("Task-style launch chooses a concrete server handle when auto is absent", async () => {
    const model = await resolveSubagentModel({
      recommendedModel: "auto",
      availableHandles: new Set(["openai/gpt-5.4-mini"]),
    });

    const args = buildSubagentArgs(
      "explore",
      exploreConfig,
      model,
      "Find the messaging agent.",
    );

    expect(model).toBe("openai/gpt-5.4-mini");
    expect(args).toContain("openai/gpt-5.4-mini");
    expect(args).not.toContain("letta/auto");
  });

  test("free-tier auto-fast recommendation falls back to a concrete handle when auto handles are absent", async () => {
    const model = await resolveSubagentModel({
      billingTier: "free",
      recommendedModel: "auto-fast",
      availableHandles: new Set(["openai/gpt-5.4-mini"]),
    });

    expect(model).toBe("openai/gpt-5.4-mini");
  });

  test("letta/auto not-found errors are retryable subagent model failures", () => {
    const errorText =
      'NotFoundError2: 404 {"detail":"NOT_FOUND: Handle letta/auto not found, must be one of []"}';

    expect(isSubagentModelUnavailableError(errorText)).toBe(true);
  });
});
