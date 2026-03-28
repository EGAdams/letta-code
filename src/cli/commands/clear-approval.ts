// Command to clear stuck approval state
// For use when approval_request_message exists but should be discarded

import type { MessageCreate } from "@letta-ai/letta-client/resources/agents/agents";
import type {
  ApprovalCreate,
  Message,
} from "@letta-ai/letta-client/resources/agents/messages";
import { getClient } from "../../agent/client";
import { getCurrentAgentId } from "../../agent/context";
import { debugWarn } from "../../utils/debug";

/**
 * Attempt to clear a stuck approval by denying all pending approvals.
 * This sends auto-deny responses for any pending approval_request_messages
 * found in the agent's recent history.
 */
export async function clearStuckApproval(): Promise<string> {
  const client = await getClient();
  const agentId = getCurrentAgentId();

  if (!agentId) {
    throw new Error("No agent ID set. Use /connect or /init first.");
  }

  try {
    const agent = await client.agents.retrieve(agentId);

    // First try: fetch recent messages to find approval_request_message
    let approvalMessage: Message | null = null;
    const msgPage = await client.agents.messages.list(agentId, {
      limit: 100,
      order: "desc",
    });
    const messages = msgPage.getPaginatedItems();

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      if (msg && msg.message_type === "approval_request_message") {
        approvalMessage = msg;
        break;
      }
    }

    // Fallback: check in_context_message_ids (Letta 0.16.x quirk)
    if (!approvalMessage) {
      const agentStateAny = agent as unknown as {
        in_context_message_ids?: string[] | null;
      };
      const lastInContextId = agentStateAny.in_context_message_ids?.at(-1);
      if (lastInContextId) {
        try {
          const retrieved = await client.messages.retrieve(lastInContextId);
          const approvalVariant =
            retrieved.find(
              (m) => m.message_type === "approval_request_message",
            ) || null;
          if (approvalVariant) {
            approvalMessage = approvalVariant;
          }
        } catch (e) {
          // Ignore retrieval error, will handle below
        }
      }
    }

    if (!approvalMessage) {
      return (
        "ℹ️ No approval_request_message found in recent history or in_context_message_ids.\n" +
        "The approval state may already be cleared."
      );
    }

    // Extract tool call IDs to deny
    const approvalMsgAny = approvalMessage as unknown as {
      tool_calls?: Array<{ tool_call_id?: string }>;
      tool_call?: { tool_call_id?: string };
    };
    const toolCalls = Array.isArray(approvalMsgAny.tool_calls)
      ? approvalMsgAny.tool_calls
      : approvalMsgAny.tool_call
        ? [approvalMsgAny.tool_call]
        : [];

    const toolCallIds = toolCalls
      .map((tc) => tc?.tool_call_id)
      .filter((id): id is string => !!id);

    if (toolCallIds.length === 0) {
      return (
        "ℹ️ Approval message found but has no tool call IDs to deny.\n" +
        "This is unexpected. Try restarting the CLI."
      );
    }

    debugWarn(
      "clear-approval",
      `Found ${toolCallIds.length} tool call(s) to deny in approval message ${approvalMessage.id}`,
    );

    // Build denial responses
    const denialResponses: ApprovalCreate[] = toolCallIds.map((id) => ({
      type: "approval",
      tool_call_id: id,
      approved: false,
    }));

    // Send denials to clear the stuck state
    // Use conversations API with agent_id in body (for Letta 0.16.x compatibility)
    const input: Array<MessageCreate | ApprovalCreate> = [...denialResponses];

    const response = await client.conversations.messages.create("default", {
      messages: input,
      streaming: false,
      stream_tokens: false,
      background: true,
      agent_id: agentId,
    });

    const respAny = response as unknown as {
      messages?: Array<{ message_type?: string }>;
    };
    const respMessages = respAny.messages || [];

    const lines = [
      `✓ Sent ${toolCallIds.length} auto-denial(s) to clear the stuck approval state.`,
      `  Response contained ${respMessages.length} message(s).`,
      `\nYou should now be able to send messages again.`,
      `If you still get the CONFLICT error, try restarting the CLI (Ctrl+C).`,
    ];

    return lines.join("\n");
  } catch (error) {
    debugWarn(
      "clear-approval",
      `Clear attempt failed: ${error instanceof Error ? error.message : String(error)}`,
    );
    throw error;
  }
}
