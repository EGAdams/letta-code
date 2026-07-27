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
    postJSON = async (url, body) => {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      if (!response.ok) {
        throw new Error(
          data?.error || `${response.status} ${response.statusText}`,
        );
      }
      return data;
    },
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
    if (typeof postJSON !== "function") {
      throw new TypeError("DashboardStatementReviewActions requires postJSON");
    }
    this._listAgents = listAgents;
    this._openAgentInput = openAgentInput;
    this._openUrl = openUrl;
    this._postJSON = postJSON;
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
  async showDocument(documentUrl, review) {
    if (documentUrl) {
      this._openUrl(documentUrl);
      return;
    }

    const payload = this._supportingDocumentPayload(review);
    if (!payload) {
      throw new Error("The offending document is no longer available.");
    }

    const result = await this._postJSON(
      "/api/open-supporting-document",
      payload,
    );
    if (!result?.ok || !result?.url) {
      throw new Error(
        result?.error || "The offending document is no longer available.",
      );
    }
    this._openUrl(result.url);
  }

  _supportingDocumentPayload(review) {
    if (!review || review.expense_id == null || review.expense_id === "") {
      return null;
    }
    const date = review.expense_date || review.date || "";
    const amount = review.amount ?? review.signed_amount ?? "";
    const description = review.description || "";
    const vendorKey = review.vendor_key || "";
    const normalizedAmount = this._normalizeSignedAmount(amount);
    if (!date || !normalizedAmount) {
      return null;
    }
    return {
      expense_id: review.expense_id,
      date,
      signed_amount: normalizedAmount,
      vendor_key: vendorKey,
      document_type: "source",
      description,
    };
  }

  _normalizeSignedAmount(amount) {
    const raw = String(amount ?? "").trim();
    if (!raw) return "";
    const normalized = raw.replace(/[$,\s]/g, "");
    if (!normalized) return "";
    if (normalized.startsWith("-")) return normalized;
    if (normalized.startsWith("+")) return `-${normalized.slice(1)}`;
    return `-${normalized}`;
  }
}
