import { StatementReviewActions } from "../abstract/statement-review-actions.interface.js";

/**
 * Browser/dashboard adapter for StatementReviewActions.
 *
 * Agent discovery and navigation are injected functions because the AM facade
 * belongs to dashboard-boot.js. This adapter translates the abstract dialog
 * operations into that facade's Input Options API and the browser URL opener.
 */
export class DashboardStatementReviewActions extends StatementReviewActions {
  constructor({
    listAgents,
    openAgentInput,
    openUrl = (url) => globalThis.open?.(url, "_blank", "noopener,noreferrer"),
  } = {}) {
    super();
    if (typeof listAgents !== "function") {
      throw new TypeError(
        "DashboardStatementReviewActions requires listAgents",
      );
    }
    if (typeof openAgentInput !== "function") {
      throw new TypeError(
        "DashboardStatementReviewActions requires openAgentInput",
      );
    }
    if (typeof openUrl !== "function") {
      throw new TypeError("DashboardStatementReviewActions requires openUrl");
    }
    this._listAgents = listAgents;
    this._openAgentInput = openAgentInput;
    this._openUrl = openUrl;
  }

  /** @override */
  async askMazda(prompt, _review) {
    const agents = (await this._listAgents()) || [];
    const mazda = agents.find(
      (agent) => String(agent.name).toLowerCase() === "mazda",
    );
    if (!mazda) throw new Error("Mazda is not in the agent list.");

    const inputOptions = await this._openAgentInput(mazda.id);
    if (!inputOptions?.setText) {
      throw new Error("Mazda's Input Options page did not open.");
    }
    inputOptions.setText(prompt);
    inputOptions.textarea?.focus();
  }

  /** @override */
  showDocument(documentUrl, _review) {
    if (!documentUrl) {
      throw new Error("The offending document is no longer available.");
    }
    this._openUrl(documentUrl);
  }
}
