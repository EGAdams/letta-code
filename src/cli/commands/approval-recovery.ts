// Diagnostic command for stuck approval states
// Helps identify and resolve "CONFLICT: waiting for approval" errors on Letta 0.16.x

import type { Message } from "@letta-ai/letta-client/resources/agents/messages";
import { getResumeData } from "../../agent/check-approval";
import { getClient } from "../../agent/client";
import { getCurrentAgentId } from "../../agent/context";
import { debugWarn } from "../../utils/debug";

export interface ApprovalRecoveryResult {
  agentId: string;
  hasPendingApprovals: boolean;
  pendingApprovals: Array<{
    toolName: string;
    toolCallId: string;
  }>;
  foundConversationId?: string;
  recommendation: string;
  debugInfo?: {
    recentMessages: Array<{
      id: string;
      type: string;
      date?: string;
      conversationId?: string;
    }>;
    agentState?: {
      in_context_message_ids: string[] | null;
    };
  };
}

export async function diagnoseApprovalState(): Promise<ApprovalRecoveryResult> {
  const client = await getClient();
  const agentId = getCurrentAgentId();

  if (!agentId) {
    throw new Error("No agent ID set. Use /connect or /init first.");
  }

  try {
    const agent = await client.agents.retrieve(agentId);

    // Get resume data which scans for approvals in all conversations (fallback scan)
    const resumeData = await getResumeData(client, agent, undefined, {
      includeMessageHistory: false,
    });

    const hasPending = resumeData.pendingApprovals.length > 0;

    // Fetch recent messages to understand state
    let recentMessages: Message[] = [];
    try {
      const msgPage = await client.agents.messages.list(agentId, {
        limit: 50,
        order: "desc",
      });
      recentMessages = msgPage.getPaginatedItems();
    } catch (e) {
      debugWarn(
        "approval-recovery",
        `Failed to fetch recent messages: ${e instanceof Error ? e.message : String(e)}`,
      );
    }

    // Check if approval_request_message exists in the fetched messages
    const hasApprovalMessageInRecent = recentMessages.some(
      (m) => m.message_type === "approval_request_message",
    );

    // Try to fetch the last in_context_message directly (if available)
    let inContextMessage: Message | null = null;
    const agentStateAny = agent as unknown as {
      in_context_message_ids?: string[] | null;
    };
    const inContextIds = agentStateAny.in_context_message_ids;
    const lastInContextId = inContextIds?.at(-1);

    if (lastInContextId) {
      try {
        const retrieved = await client.messages.retrieve(lastInContextId);
        const approvalVariant = retrieved.find(
          (m) => m.message_type === "approval_request_message",
        );
        if (approvalVariant) {
          inContextMessage = approvalVariant;
        }
      } catch (e) {
        debugWarn(
          "approval-recovery",
          `Failed to fetch in_context message ${lastInContextId}: ${e instanceof Error ? e.message : String(e)}`,
        );
      }
    }

    let recommendation = "";
    if (hasPending && resumeData.foundConversationId) {
      recommendation =
        `✓ Found pending approval in conversation: ${resumeData.foundConversationId}\n` +
        `  The CLI should automatically switch to this conversation when you try to send a message.`;
    } else if (hasPending) {
      recommendation =
        `⚠️ Found pending approval(s) but couldn't determine the conversation.\n` +
        `  Try: Restart the CLI (Ctrl+C) to force re-detection.`;
    } else if (inContextMessage) {
      recommendation =
        `⚠️ Found approval via in_context_message_ids (not in message list)!\n` +
        `  This is a Letta server quirk. Approval exists but wasn't in recent messages.\n` +
        `  Try: /clear-approval to force-deny and clear the state.`;
    } else if (
      !hasApprovalMessageInRecent &&
      inContextIds &&
      inContextIds.length > 0
    ) {
      recommendation =
        `⚠️ Agent has in_context_message_ids but no approval_request_message found.\n` +
        `  The approval may be outside the recent message window.\n` +
        `  Try: /clear-approval or restart the CLI.`;
    } else {
      recommendation =
        `⚠️ No pending approvals found, but server still reports conflict.\n` +
        `  This indicates a state mismatch. Possible causes:\n` +
        `  1. Approval state is corrupted on server\n` +
        `  2. Approval exists in unreachable conversation\n` +
        `  Try: /clear-approval or restart the CLI.`;
    }

    const result: ApprovalRecoveryResult = {
      agentId,
      hasPendingApprovals: hasPending,
      pendingApprovals: resumeData.pendingApprovals.map((approval) => ({
        toolName: approval.toolName,
        toolCallId: approval.toolCallId,
      })),
      foundConversationId: resumeData.foundConversationId,
      recommendation,
      debugInfo: {
        recentMessages: recentMessages.map((msg) => ({
          id: msg.id || "(unknown)",
          type: msg.message_type || "(unknown)",
          date: msg.date,
          conversationId: (msg as unknown as { conversation_id?: string })
            .conversation_id,
        })),
        agentState: {
          in_context_message_ids: inContextIds ?? null,
        },
      },
    };

    // Debug output
    debugWarn(
      "approval-recovery",
      `Diagnostic complete: ${hasPending ? "PENDING" : "CLEAR"} | in_context_found: ${inContextMessage ? "YES" : "NO"} | recent_messages: ${recentMessages.length}`,
    );

    return result;
  } catch (error) {
    debugWarn(
      "approval-recovery",
      `Diagnostic failed: ${error instanceof Error ? error.message : String(error)}`,
    );
    throw error;
  }
}
