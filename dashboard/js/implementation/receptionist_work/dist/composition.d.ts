import type { ConversationAgent } from "../../../abstract/conversation-agent.interface.js";
import { OperationalConversationAgent } from "./conversation.js";
import type { JsonHttp } from "./interfaces.js";
export declare function createOperationalConversation({
  inner,
  http,
  doc,
}: {
  inner: ConversationAgent;
  http: JsonHttp;
  doc: Document;
}): {
  agent: OperationalConversationAgent;
  mount(): void;
};
