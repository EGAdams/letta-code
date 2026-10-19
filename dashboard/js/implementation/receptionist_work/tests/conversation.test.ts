import { expect, test } from "bun:test";
import {
  AgentEventKind,
  agentEvent,
  ConversationAgent,
} from "../../../abstract/conversation-agent.interface.js";
import { commandFrom, workFrom } from "../src/contracts.js";
import { OperationalConversationAgent } from "../src/conversation.js";
import { TurnRequestIdentity } from "../src/request-identity.js";

const identities = { forGeneration: (_generation: string) => "operation-0001" };

const command = {
  id: "category-0001",
  action: "category" as const,
  expense_id: 900001,
  category_id: 425,
  category_label: "Walgreens (RM) [425]",
  url: "",
  expected: {},
};
const work = {
  ok: true,
  error: "",
  state: {
    workspace: "toyota",
    assignment: "tax_issues",
    environment: "training" as const,
    status: "waiting_browser",
    message: "Opening editor",
    expense_id: 900001,
    command,
    history: [],
    run_ids: [],
  },
};
class Inner extends ConversationAgent {
  override async *submit(_turn: unknown, generation: string) {
    yield agentEvent(AgentEventKind.TOOL_RESULT, "", generation, {
      name: "receptionist_work",
      detail: { work },
    })!;
    yield agentEvent(
      AgentEventKind.ASSISTANT_TEXT,
      "I'll save and check.",
      generation,
    )!;
    yield agentEvent(AgentEventKind.TERMINAL, "", generation)!;
  }
  override cancel() {}
}
test("tools stay out of speech and success follows browser execution plus verification", async () => {
  const calls: string[] = [];
  const browser = {
    show() {},
    async execute() {
      calls.push("browser");
      return { ok: true, error: "" };
    },
  };
  const workflows = {
    async state() {
      return work;
    },
    async claim() {
      calls.push("claim");
      return true;
    },
    async verify() {
      calls.push("verify");
      return {
        ...work,
        state: {
          ...work.state,
          command: null,
          message: "Verified stored category",
        },
      };
    },
    async cancel() {
      return work;
    },
  };
  const agent = new OperationalConversationAgent(
    new Inner(),
    workflows,
    browser,
    identities,
  );
  const events = [];
  for await (const event of agent.submit(
    { agent: "toyota", text: "Set to Walgreens (RM)" },
    "one",
  ))
    events.push(event);
  expect(calls).toEqual(["claim", "browser", "verify"]);
  expect(
    events.filter((e) => e.kind === "assistant_text").map((e) => e.text),
  ).toEqual(["I'll save and check.", "Verified stored category"]);
});
test("a command already claimed in another browser is not executed again", async () => {
  let saves = 0;
  const browser = {
    show() {},
    async execute() {
      saves++;
      return { ok: true, error: "" };
    },
  };
  const workflows = {
    async state() {
      return work;
    },
    async claim() {
      return false;
    },
    async verify() {
      throw Error("must not verify other's running save");
    },
    async cancel() {
      return work;
    },
  };
  const agent = new OperationalConversationAgent(
    new Inner(),
    workflows,
    browser,
    identities,
  );
  for await (const _ of agent.submit(
    { agent: "toyota", text: "change category" },
    "one",
  )) {
  }
  expect(saves).toBe(0);
});
test("browser commands reject external evidence URLs and non-training work", () => {
  expect(
    commandFrom({ ...command, action: "evidence", url: "https://example.com" }),
  ).toBeNull();
  expect(
    workFrom({ ...work, state: { ...work.state, environment: "live" } }),
  ).toBeNull();
});
test("cancellation while claiming a browser command prevents the subsequent save", async () => {
  let saves = 0,
    cancelled = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let claimed!: () => void;
  const started = new Promise<void>((resolve) => {
    claimed = resolve;
  });
  const workflows = {
    async state() {
      return work;
    },
    async claim() {
      claimed();
      await gate;
      return true;
    },
    async verify() {
      throw Error("must not verify an unstarted save");
    },
    async cancel() {
      cancelled++;
      return work;
    },
  };
  const browser = {
    show() {},
    async execute() {
      saves++;
      return { ok: true, error: "" };
    },
  };
  const agent = new OperationalConversationAgent(
    new Inner(),
    workflows,
    browser,
    identities,
  );
  const drain = (async () => {
    for await (const _ of agent.submit(
      { agent: "toyota", text: "change category" },
      "one",
    )) {
    }
  })();
  await started;
  agent.cancel("one");
  release();
  await drain;
  expect(saves).toBe(0);
  expect(cancelled).toBe(1);
});
test("voice generation retries keep one ID while new page sessions get fresh IDs", () => {
  let sequence = 0;
  const create = () => `operation-${++sequence}`;
  const first = new TurnRequestIdentity(create);
  expect(first.forGeneration("gen-2")).toBe(first.forGeneration("gen-2"));
  const second = new TurnRequestIdentity(create);
  expect(second.forGeneration("gen-2")).not.toBe(first.forGeneration("gen-2"));
});
