import { expect, test } from "bun:test";
import { type WorkState, workFrom } from "../src/contracts.js";
import { TrainingWorkPresenter } from "../src/presentation.js";

const SERVER_STATUSES = [
  "idle",
  "ready",
  "waiting_browser",
  "verified",
  "paused",
  "cancelled",
  "needs_input",
  "failed",
] as const;

const command = {
  id: "category-0001",
  action: "category" as const,
  expense_id: 900001,
  category_id: 425,
  category_label: "Walgreens (RM) [425]",
  url: "",
  expected: { version: "v7" },
};

function state(overrides: Partial<WorkState> = {}): WorkState {
  return {
    workspace: "toyota",
    assignment: "tax_issues",
    environment: "training",
    status: "ready",
    message: "Expense #900001 is selected.",
    expense_id: 900001,
    question: "",
    category: "",
    command: null,
    history: [],
    run_ids: ["a1b2c3d4"],
    ...overrides,
  };
}
const present = (overrides: Partial<WorkState> = {}) =>
  new TrainingWorkPresenter().present(state(overrides));

test("every status the server can send is described distinctly", () => {
  const facts = SERVER_STATUSES.map((status) => present({ status }));
  expect(new Set(facts.map((fact) => fact.phase)).size).toBe(
    SERVER_STATUSES.length,
  );
  expect(new Set(facts.map((fact) => fact.headline)).size).toBe(
    SERVER_STATUSES.length,
  );
  for (const fact of facts) expect(fact.headline.length).toBeGreaterThan(0);
});

test("only an independently verified status reads as a completed save", () => {
  for (const status of SERVER_STATUSES) {
    const fact = present({
      status,
      command: status === "verified" ? null : command,
    });
    expect(fact.verified).toBe(status === "verified");
    expect(fact.evidence.length > 0).toBe(status === "verified");
  }
});

test("verified evidence names the record and its stored category so the claim can be checked", () => {
  const fact = present({
    status: "verified",
    category: "Walgreens (RM) [425]",
    message: "Verified training expense #900001",
    command: null,
  });
  expect(fact.evidence).toContain("900001");
  expect(fact.evidence).toContain("Walgreens (RM) [425]");
});

test("evidence is tied to the operation and run identity that produced it", () => {
  const fact = present({
    status: "verified",
    command: null,
    run_ids: ["0000aaaa", "a1b2c3d4"],
  });
  expect(fact.identity).toContain("a1b2c3d4");
  expect(present({ status: "waiting_browser", command }).identity).toContain(
    "category-0001",
  );
});

test("waiting for input shows the question and never claims progress", () => {
  const fact = present({
    status: "needs_input",
    question: "Should this be Walgreens (RM) or Walgreens (RJ)?",
  });
  expect(fact.waitingFor).toContain("Walgreens (RJ)");
  expect(fact.verified).toBe(false);
  expect(fact.phase).toBe("needs_input");
});

test("a failure reports the problem and does not read as a save", () => {
  const fact = present({
    status: "failed",
    message: "The editor did not acknowledge its operation.",
  });
  expect(fact.problem).toContain("did not acknowledge");
  expect(fact.headline.toLowerCase()).not.toContain("verified");
  expect(fact.headline.toLowerCase()).not.toContain("saved");
});

test("cancellation says plainly that an earlier save is retained", () => {
  expect(present({ status: "cancelled" }).problem).toMatch(
    /retained|already saved/i,
  );
});

test("the assignment and expense are named in readable words, including when absent", () => {
  expect(present().assignment).toBe("Tax issues");
  expect(present({ assignment: "" }).assignment).toMatch(/no assignment/i);
  expect(present().expense).toContain("#900001");
  expect(present({ expense_id: null }).expense).toMatch(/no expense/i);
});

test("the requested operation is described, or explicitly absent", () => {
  expect(present({ command }).operation).toContain("Walgreens (RM) [425]");
  expect(present({ command }).operation.toLowerCase()).toContain("category");
  expect(
    present({
      command: {
        ...command,
        action: "evidence",
        url: "/api/receptionist-training/document?expense_id=900001",
      },
    }).operation.toLowerCase(),
  ).toContain("supporting");
  expect(
    present({
      command: { ...command, action: "editor" },
    }).operation.toLowerCase(),
  ).toContain("editor");
  expect(present({ command: null }).operation).toMatch(/no operation/i);
});

test("an unrecognised status is reported as unexpected rather than as success", () => {
  const fact = present({ status: "something_new" as WorkState["status"] });
  expect(fact.phase).toBe("unknown");
  expect(fact.verified).toBe(false);
  expect(fact.headline).toMatch(/unexpected|unknown/i);
});

test("the decoded work state carries the question and stored category the panel has to show", () => {
  const decoded = workFrom({
    ok: true,
    error: "",
    state: {
      ...state({
        status: "needs_input",
        question: "Which Walgreens category?",
        category: "Walgreens (RM) [425]",
      }),
    },
  });
  expect(decoded?.state.question).toBe("Which Walgreens category?");
  expect(decoded?.state.category).toBe("Walgreens (RM) [425]");
  const sloppy = workFrom({
    ok: true,
    error: "",
    state: { ...state(), question: 7, category: null },
  });
  expect(sloppy?.state.question).toBe("");
  expect(sloppy?.state.category).toBe("");
});
