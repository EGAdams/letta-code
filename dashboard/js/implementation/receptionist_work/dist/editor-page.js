import { ExpenseEditPanel } from "../../expense-edit-panel.js";
import { commandFrom } from "./contracts.js";

/** Decorator for the editor's HTTP port; only the destination changes. */
class TrainingEditorHttp {
  operationId = "";
  async getJSON(url) {
    return this.request(url);
  }
  async postJSON(url, body) {
    return this.request(url, {
      ...body,
      ...(url === "/api/expense-edit"
        ? { operation_id: this.operationId }
        : {}),
    });
  }
  async request(url, body) {
    const allowed = [
      "/api/expense-categories",
      "/api/expense-search",
      "/api/expense-edit",
    ];
    if (!allowed.includes(url))
      throw new Error("This training editor supports category changes only.");
    const response = await fetch(
      url.replace("/api/", "/api/receptionist-training/"),
      {
        method: body ? "POST" : "GET",
        headers: { "Content-Type": "application/json" },
        ...(body ? { body: JSON.stringify(body) } : {}),
      },
    );
    const result = await response.json();
    if (!response.ok)
      throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
}
const root = document.getElementById("training-editor-root");
const trace = new URLSearchParams(window.location.search).get("trace");
if (root && trace) {
  const response = await fetch(
    `/api/receptionist-work/trace?run=${encodeURIComponent(trace)}`,
  );
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(await response.json(), null, 2);
  root.appendChild(pre);
} else if (root) {
  const http = new TrainingEditorHttp();
  const panel = new ExpenseEditPanel({ http, root, expanded: true });
  await panel.mount();
  window.addEventListener("message", async (event) => {
    if (
      event.source !== window.parent ||
      event.origin !== window.location.origin ||
      event.data?.channel !== "toyota-editor-command"
    )
      return;
    const command = commandFrom(event.data.command);
    if (!command || command.action === "evidence") return;
    let ok = false,
      error = "";
    try {
      if (panel.dialog.selectedId !== command.expense_id)
        throw new Error("The opened editor is for a different expense.");
      if (command.action === "category") {
        http.operationId = command.id;
        panel.dialog.selectCategory(command.category_id);
        const result = await panel.dialog.saveChanges();
        if (!result?.ok)
          throw new Error(result?.error || "The editor refused those values.");
      }
      ok = true;
    } catch (cause) {
      error = String(cause);
    }
    window.parent.postMessage(
      { channel: "toyota-editor-result", id: command.id, ok, error },
      window.location.origin,
    );
  });
  window.parent.postMessage(
    {
      channel: "toyota-editor-ready",
      operation_id: new URLSearchParams(window.location.search).get(
        "operation_id",
      ),
    },
    window.location.origin,
  );
}
