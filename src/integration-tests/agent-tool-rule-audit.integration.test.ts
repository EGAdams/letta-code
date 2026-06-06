import { beforeAll, describe, expect, test } from "bun:test";
import { getClient } from "../agent/client";
import { settingsManager } from "../settings-manager";
import { findHangingToolRules } from "../tools/toolset";

/**
 * Production guard for the Scissari↔Frita "stuck in a tool loop / I've reset our
 * conversation" cycle (2026-06-05).
 *
 * Frita was a `letta_v1_agent` carrying `{ type: "required_before_exit",
 * tool_name: "send_message" }`. Because a `letta_v1_agent` ends its turn with an
 * assistant message and never calls `send_message`, the rule could never be
 * satisfied: the server looped on `ToolRuleViolated` heartbeats until
 * `max_steps` and returned no reply, trapping any agent that messaged her.
 *
 * This test sweeps EVERY agent on the target server and fails if any of them
 * carries a hang-inducing tool rule — i.e. it would have caught Frita before a
 * human ever noticed the Telegram reset loop. It is read-only.
 *
 * Run against the live server:
 *   bun test src/integration-tests/agent-tool-rule-audit.integration.test.ts
 *   LETTA_BASE_URL=http://localhost:8283 LETTA_API_KEY=... bun test src/integration-tests/agent-tool-rule-audit.integration.test.ts
 *
 * If no server is reachable the test skips gracefully (passes as a no-op).
 */

const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";

// Safety cap so a misbehaving server can't make the sweep run forever.
const MAX_AGENTS = 5000;

describe("agent tool-rule audit (server-wide)", () => {
  beforeAll(async () => {
    process.env.LETTA_BASE_URL = process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
    process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
    await settingsManager.initialize();
  });

  test("no agent carries a hang-inducing tool rule (send_message required_before_exit on a message-terminated agent)", async () => {
    const client = await getClient();

    type Offender = {
      id: string;
      name: string;
      agent_type: string;
      rules: string[];
    };
    const offenders: Offender[] = [];

    let scanned = 0;
    try {
      const page = await client.agents.list({ limit: 100 });
      for await (const agent of page) {
        scanned += 1;
        if (scanned > MAX_AGENTS) break;
        const hits = findHangingToolRules(agent);
        if (hits.length > 0) {
          offenders.push({
            id: agent.id,
            name: agent.name,
            agent_type: agent.agent_type,
            rules: hits.map((r) => `${r.type}:${r.tool_name ?? "<none>"}`),
          });
        }
      }
    } catch (err) {
      // No reachable server in this environment — skip rather than fail.
      console.warn(
        `[agent-tool-rule-audit] Skipping: could not reach Letta server at ` +
          `${process.env.LETTA_BASE_URL}: ${err instanceof Error ? err.message : String(err)}`,
      );
      return;
    }

    console.log(
      `[agent-tool-rule-audit] Scanned ${scanned} agent(s); ` +
        `${offenders.length} with hang-inducing tool rules.`,
    );

    if (offenders.length > 0) {
      const detail = offenders
        .map(
          (o) =>
            `  - ${o.name} (${o.id}) [${o.agent_type}] -> ${o.rules.join(", ")}`,
        )
        .join("\n");
      throw new Error(
        `Found ${offenders.length} agent(s) that will hang on every turn / inbound message.\n` +
          `Fix each with: UPDATE agents SET tool_rules='[]'::jsonb WHERE id='<id>'; ` +
          `(or remove only the send_message required_before_exit rule).\n${detail}`,
      );
    }

    expect(offenders).toEqual([]);
  });
});
