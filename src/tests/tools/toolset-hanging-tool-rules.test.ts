import { describe, expect, test } from "bun:test";

import { findHangingToolRules, hasHangingToolRules } from "../../tools/toolset";

// Regression coverage for the Scissari↔Frita "stuck in a tool loop / I've reset
// our conversation" cycle (2026-06-05).
//
// Frita was a `letta_v1_agent` carrying a tool rule of
//   { type: "required_before_exit", tool_name: "send_message" }
// A `letta_v1_agent` ends its turn with an assistant message and never calls
// `send_message`, so the rule could never be satisfied. The server emitted
// endless `ToolRuleViolated` heartbeats until `max_steps`, returning no reply —
// which trapped any agent that messaged her and produced a ~2-minute reset loop.
//
// biome-ignore lint/suspicious/noExplicitAny: test fixtures are loose agent shapes
const agent = (agent_type: string, tool_rules: any[]) =>
  ({ agent_type, tool_rules }) as never;

const HANGING_RULE = {
  type: "required_before_exit",
  tool_name: "send_message",
  prompt_template: null,
};

describe("findHangingToolRules", () => {
  test("flags send_message required_before_exit on a letta_v1_agent (the Frita bug)", () => {
    const hits = findHangingToolRules(agent("letta_v1_agent", [HANGING_RULE]));
    expect(hits).toHaveLength(1);
    expect(hits[0]?.tool_name).toBe("send_message");
    expect(hasHangingToolRules(agent("letta_v1_agent", [HANGING_RULE]))).toBe(
      true,
    );
  });

  test("flags the same rule on a react_agent", () => {
    expect(hasHangingToolRules(agent("react_agent", [HANGING_RULE]))).toBe(
      true,
    );
  });

  test("does NOT flag a healthy letta_v1_agent with no tool rules (like Scissari)", () => {
    expect(findHangingToolRules(agent("letta_v1_agent", []))).toEqual([]);
    expect(hasHangingToolRules(agent("letta_v1_agent", []))).toBe(false);
  });

  test("does NOT flag memgpt agents — they legitimately end turns via send_message", () => {
    expect(hasHangingToolRules(agent("memgpt_agent", [HANGING_RULE]))).toBe(
      false,
    );
    expect(hasHangingToolRules(agent("memgpt_v2_agent", [HANGING_RULE]))).toBe(
      false,
    );
  });

  test("does NOT flag unrelated rules on a letta_v1_agent", () => {
    expect(
      hasHangingToolRules(
        agent("letta_v1_agent", [
          { type: "requires_approval", tool_name: "Bash" },
          { type: "continue", tool_name: "fetch_webpage" },
          // required_before_exit on a tool the agent CAN call is fine.
          { type: "required_before_exit", tool_name: "Bash" },
        ]),
      ),
    ).toBe(false);
  });

  test("tolerates missing/empty fields without throwing", () => {
    // biome-ignore lint/suspicious/noExplicitAny: deliberately malformed input
    expect(findHangingToolRules({} as any)).toEqual([]);
    // biome-ignore lint/suspicious/noExplicitAny: deliberately malformed input
    expect(findHangingToolRules({ agent_type: null } as any)).toEqual([]);
    expect(
      // biome-ignore lint/suspicious/noExplicitAny: deliberately malformed input
      findHangingToolRules({ agent_type: "letta_v1_agent" } as any),
    ).toEqual([]);
  });

  test("isolates only the offending rule when mixed with healthy ones", () => {
    const hits = findHangingToolRules(
      agent("letta_v1_agent", [
        { type: "requires_approval", tool_name: "Task" },
        HANGING_RULE,
        { type: "continue", tool_name: "web_search" },
      ]),
    );
    expect(hits).toHaveLength(1);
    expect(hits[0]?.type).toBe("required_before_exit");
  });
});
