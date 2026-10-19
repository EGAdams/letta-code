import { DashboardBrowserWorkspace } from "./browser-workspace.js";
import { OperationalConversationAgent } from "./conversation.js";
import {
  newBrowserRequestId,
  TurnRequestIdentity,
} from "./request-identity.js";
import { DashboardWorkflows } from "./workflows.js";
export function createOperationalConversation({ inner, http, doc }) {
  const root = doc.createElement("section");
  root.id = "receptionist-work";
  const browser = new DashboardBrowserWorkspace(root, doc);
  const workflows = new DashboardWorkflows(http, newBrowserRequestId());
  const agent = new OperationalConversationAgent(
    inner,
    workflows,
    browser,
    new TurnRequestIdentity(newBrowserRequestId),
  );
  return {
    agent,
    mount() {
      doc.getElementById("receptionist-box")?.appendChild(root);
      void workflows
        .state()
        .then((work) => {
          browser.show(work.state);
          if (work.state.command) {
            const button = doc.createElement("button");
            button.textContent = "Check interrupted operation";
            button.addEventListener("click", async () => {
              button.disabled = true;
              try {
                const result = await workflows.verify(work.state.command, {
                  ok: false,
                  error: "Browser reconnected; checking the stored outcome.",
                });
                browser.show(result.state);
              } catch (error) {
                button.textContent = String(error);
              } finally {
                button.disabled = false;
              }
            });
            root.appendChild(button);
          }
        })
        .catch((error) => {
          root.textContent = `Workflow service unavailable: ${String(error)}`;
        });
    },
  };
}
