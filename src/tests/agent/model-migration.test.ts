import { describe, expect, test } from "bun:test";

import {
  getResolvedModelHandleForAgent,
  getResumeModelMigrationHandle,
  getUpdateArgsForModelHandle,
} from "../../agent/model";

describe("resume model migration", () => {
  test("normalizes current chatgpt_oauth handle from llm_config", () => {
    expect(
      getResolvedModelHandleForAgent({
        llm_config: {
          model_endpoint_type: "chatgpt_oauth",
          model: "gpt-5.2-codex",
        },
      }),
    ).toBe("chatgpt-plus-pro/gpt-5.2-codex");
  });

  test("recommends migrating legacy unsupported chatgpt codex handle", () => {
    expect(
      getResumeModelMigrationHandle({
        model: "chatgpt-plus-pro/gpt-5.2-codex",
      }),
    ).toBe("chatgpt-plus-pro/gpt-5.3-codex");
  });

  test("does not migrate already supported chatgpt codex handle", () => {
    expect(
      getResumeModelMigrationHandle({
        model: "chatgpt-plus-pro/gpt-5.3-codex",
      }),
    ).toBeNull();
  });

  test("preserves reasoning-tier update args for migrated handle", () => {
    expect(
      getUpdateArgsForModelHandle("chatgpt-plus-pro/gpt-5.3-codex", {
        reasoning_effort: "medium",
      }),
    ).toMatchObject({
      reasoning_effort: "medium",
    });
  });
});
