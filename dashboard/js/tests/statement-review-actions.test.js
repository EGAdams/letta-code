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

  test("delegates document display to the injected browser opener", () => {
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
