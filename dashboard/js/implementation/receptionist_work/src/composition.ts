import type { ConversationAgent } from "../../../abstract/conversation-agent.interface.js";
import { DashboardBrowserWorkspace } from "./browser-workspace.js";
import { OperationalConversationAgent } from "./conversation.js";
import type { JsonHttp } from "./interfaces.js";
import {
  newBrowserRequestId,
  TurnRequestIdentity,
} from "./request-identity.js";
import { DashboardWorkflows } from "./workflows.js";

export function createOperationalConversation({
  inner,
  http,
  doc,
}: {
  inner: ConversationAgent;
  http: JsonHttp;
  doc: Document;
}) {
  const root = doc.createElement("section");
  root.id = "receptionist-work";
  // Hidden rather than omitted: the iframe inside still needs to be attached
  // to the document to navigate when Toyota executes a browser command, so
  // the panel is kept in the DOM and just visually removed from the front
  // page (everything from "Toyota's work — synthetic training" down).
  root.hidden = true;
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
                const result = await workflows.verify(work.state.command!, {
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
