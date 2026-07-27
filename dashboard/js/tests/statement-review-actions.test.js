import { describe, expect, test } from "bun:test";
import { StatementReviewActions } from "../abstract/statement-review-actions.interface.js";
import { DashboardStatementReviewActions } from "../implementation/dashboard-statement-review-actions.js";

describe("StatementReviewActions port", () => {
  test("abstract operations fail loudly", async () => {
    const actions = new StatementReviewActions();
    expect(() => actions.showDocument("/review.pdf", {})).toThrow(
      /showDocument\(\) is abstract/,
    );
    await expect(actions.askMazda("prompt", {})).rejects.toThrow(
      /askMazda\(\) is abstract/,
    );
  });
});

describe("DashboardStatementReviewActions adapter", () => {
  test("validates its injected ports", () => {
    expect(() => new DashboardStatementReviewActions()).toThrow(/listAgents/);
    expect(
      () =>
        new DashboardStatementReviewActions({
          listAgents: async () => [],
        }),
    ).toThrow(/openAgentInput/);
  });

  test("opens Mazda Input Options and fills its public API", async () => {
    const events = [];
    const textarea = { focus: () => events.push(["focus"]) };
    const actions = new DashboardStatementReviewActions({
      listAgents: async () => [
        { id: "agent-frita", name: "Frita" },
        { id: "agent-mazda", name: "Mazda" },
      ],
      openAgentInput: async (id) => {
        events.push(["open", id]);
        return {
          textarea,
          setText: (text) => events.push(["text", text]),
        };
      },
    });

    await actions.askMazda("complete review context", { id: "review.json" });

    expect(events).toEqual([
      ["open", "agent-mazda"],
      ["text", "complete review context"],
      ["focus"],
    ]);
  });

  test("delegates document display to the injected browser opener when given a URL", () => {
    const opened = [];
    const actions = new DashboardStatementReviewActions({
      listAgents: async () => [],
      openAgentInput: async () => null,
      openUrl: (url) => opened.push(url),
    });

    actions.showDocument("/api/statement-review-document?id=review.pdf.json");

    expect(opened).toEqual([
      "/api/statement-review-document?id=review.pdf.json",
    ]);
  });

  test("fails closed when Mazda or the document is unavailable", async () => {
    const actions = new DashboardStatementReviewActions({
      listAgents: async () => [],
      openAgentInput: async () => null,
      openUrl: () => {},
    });

    await expect(actions.askMazda("prompt", {})).rejects.toThrow(
      /Mazda is not in the agent list/,
    );
    expect(() => actions.showDocument("", {})).toThrow(
      /document is no longer available/,
    );
  });
});

test("builds a supporting-document URL from expense-backed review context", async () => {
  const opened = [];
  const posts = [];
  const actions = new DashboardStatementReviewActions({
    listAgents: async () => [],
    openAgentInput: async () => null,
    openUrl: (url) => opened.push(url),
    postJSON: async (url, body) => {
      posts.push([url, body]);
      return { ok: true, url: "/supporting-document/token#page=1" };
    },
  });

  await actions.showDocument("", {
    expense_id: 477,
    expense_date: "2025-01-13",
    amount: "25.00",
    vendor_key: "right_to_life",
    description: "Right to Life - Current president: Amber Roseboom",
  });

  expect(posts).toEqual([
    [
      "/api/open-supporting-document",
      {
        expense_id: 477,
        date: "2025-01-13",
        signed_amount: "-25.00",
        vendor_key: "right_to_life",
        document_type: "source",
        description: "Right to Life - Current president: Amber Roseboom",
      },
    ],
  ]);
  expect(opened).toEqual(["/supporting-document/token#page=1"]);
});

test("fails closed when supporting-document lookup cannot build a URL", async () => {
  const actions = new DashboardStatementReviewActions({
    listAgents: async () => [],
    openAgentInput: async () => null,
    openUrl: () => {},
    postJSON: async () => ({ ok: false, error: "missing document" }),
  });

  await expect(
    actions.showDocument("", {
      expense_id: 477,
      expense_date: "2025-01-13",
      amount: "25.00",
      vendor_key: "right_to_life",
      description: "Right to Life - Current president: Amber Roseboom",
    }),
  ).rejects.toThrow(/missing document/);
});
