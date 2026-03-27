/**
 * Utilities for sending messages to an agent via conversations
 **/

import type { Stream } from "@letta-ai/letta-client/core/streaming";
import type { MessageCreate } from "@letta-ai/letta-client/resources/agents/agents";
import type {
  ApprovalCreate,
  LettaStreamingResponse,
} from "@letta-ai/letta-client/resources/agents/messages";
import type { MessageCreateParams as ConversationMessageCreateParams } from "@letta-ai/letta-client/resources/conversations/messages";
import {
  type ClientTool,
  captureToolExecutionContext,
  type PermissionModeState,
  waitForToolsetReady,
} from "../tools/manager";
import { debugLog, debugWarn, isDebugEnabled } from "../utils/debug";
import { isTimingsEnabled } from "../utils/timing";
import {
  type ApprovalNormalizationOptions,
  normalizeOutgoingApprovalMessages,
} from "./approval-result-normalization";
import { getClient } from "./client";
import { buildClientSkillsPayload } from "./clientSkills";
import { ALL_SKILL_SOURCES } from "./skillSources";

const streamRequestStartTimes = new WeakMap<object, number>();
const streamToolContextIds = new WeakMap<object, string>();

// Cache for "default" conversations upgraded to real IDs on older servers
// (e.g. 0.16.x which requires strict "conv-{uuid}" format, 41 chars).
const defaultConvIdCache = new Map<string, string>();
export type StreamRequestContext = {
  conversationId: string;
  resolvedConversationId: string;
  agentId: string | null;
  requestStartedAtMs: number;
  otid?: string;
};
const streamRequestContexts = new WeakMap<object, StreamRequestContext>();

export function getStreamRequestStartTime(
  stream: Stream<LettaStreamingResponse>,
): number | undefined {
  return streamRequestStartTimes.get(stream as object);
}

export function getStreamToolContextId(
  stream: Stream<LettaStreamingResponse>,
): string | null {
  return streamToolContextIds.get(stream as object) ?? null;
}

export function getStreamRequestContext(
  stream: Stream<LettaStreamingResponse>,
): StreamRequestContext | undefined {
  return streamRequestContexts.get(stream as object);
}

export type SendMessageStreamOptions = {
  streamTokens?: boolean;
  background?: boolean;
  agentId?: string; // Required when conversationId is "default"
  approvalNormalization?: ApprovalNormalizationOptions;
  workingDirectory?: string;
  /** Per-conversation permission mode state. When provided, tool execution uses
   *  this scoped state instead of the global permissionMode singleton. */
  permissionModeState?: PermissionModeState;
  /**
   * Per-request model override. Uses backend request-scoped override_model and
   * does not mutate agent/conversation persisted model configuration.
   */
  overrideModel?: string;
};

export function buildConversationMessagesCreateRequestBody(
  conversationId: string,
  messages: Array<MessageCreate | ApprovalCreate>,
  opts: SendMessageStreamOptions = { streamTokens: true, background: true },
  clientTools: ClientTool[],
  clientSkills: NonNullable<
    ConversationMessageCreateParams["client_skills"]
  > = [],
) {
  const isDefaultConversation = conversationId === "default";
  if (isDefaultConversation && !opts.agentId) {
    throw new Error(
      "agentId is required in opts when using default conversation",
    );
  }

  return {
    messages: normalizeOutgoingApprovalMessages(
      messages,
      opts.approvalNormalization,
    ),
    streaming: true,
    stream_tokens: opts.streamTokens ?? true,
    include_pings: true,
    background: opts.background ?? true,
    client_skills: clientSkills,
    client_tools: clientTools,
    include_compaction_messages: true,
    ...(opts.overrideModel ? { override_model: opts.overrideModel } : {}),
    ...(isDefaultConversation ? { agent_id: opts.agentId } : {}),
  };
}

/**
 * Send a message to a conversation and return a streaming response.
 * Uses the conversations API for all conversations.
 *
 * For the "default" conversation (agent's primary message history without
 * an explicit conversation object), pass conversationId="default" and
 * provide agentId in opts. The agent id is sent in the request body.
 */
export async function sendMessageStream(
  conversationId: string,
  messages: Array<MessageCreate | ApprovalCreate>,
  opts: SendMessageStreamOptions = { streamTokens: true, background: true },
  // Disable SDK retries by default - state management happens outside the stream,
  // so retries would violate idempotency and create race conditions
  requestOptions: {
    maxRetries?: number;
    signal?: AbortSignal;
    headers?: Record<string, string>;
  } = {
    maxRetries: 0,
  },
): Promise<Stream<LettaStreamingResponse>> {
  const requestStartTime = isTimingsEnabled() ? performance.now() : undefined;
  const requestStartedAtMs = Date.now();
  const client = await getClient();

  // Wait for any in-progress toolset switch to complete before reading tools
  // This prevents sending messages with stale tools during a switch
  await waitForToolsetReady();
  const { clientTools, contextId } = captureToolExecutionContext(
    opts.workingDirectory,
    opts.permissionModeState,
  );
  const { clientSkills, errors: clientSkillDiscoveryErrors } =
    await buildClientSkillsPayload({
      agentId: opts.agentId,
      skillSources: ALL_SKILL_SOURCES,
    });

  const resolvedConversationId = conversationId;
  const requestBody = buildConversationMessagesCreateRequestBody(
    conversationId,
    messages,
    opts,
    clientTools,
    clientSkills,
  );

  if (isDebugEnabled()) {
    debugLog(
      "agent-message",
      "sendMessageStream: conversationId=%s, agentId=%s",
      conversationId,
      opts.agentId ?? "(none)",
    );

    const formattedSkills = clientSkills.map(
      (skill) => `${skill.name} (${skill.location})`,
    );
    debugLog(
      "agent-message",
      "sendMessageStream: client_skills (%d) %s",
      clientSkills.length,
      formattedSkills.length > 0 ? formattedSkills.join(", ") : "(none)",
    );

    if (clientSkillDiscoveryErrors.length > 0) {
      for (const error of clientSkillDiscoveryErrors) {
        debugWarn(
          "agent-message",
          "sendMessageStream: client_skills discovery error at %s: %s",
          error.path,
          error.message,
        );
      }
    }
  }

  const extraHeaders: Record<string, string> = {};
  if (process.env.LETTA_RESPONSES_WS === "1") {
    extraHeaders["X-Experimental-OpenAI-Responses-Websocket"] = "true";
  }

  const requestOptionsWithHeaders = {
    ...requestOptions,
    headers: {
      ...((requestOptions.headers as Record<string, string>) ?? {}),
      ...extraHeaders,
    },
  };

  const firstOtid = (messages[0] as unknown as { otid?: string })?.otid;

  // For "default" conversations, try passing "default" first (newer servers).
  // If the server rejects it (older 0.16.x servers enforce strict "conv-{uuid}"
  // format and reject both "default" and agent IDs), create a real conversation
  // on-demand and cache it per agent for the lifetime of the process.
  let stream: Stream<LettaStreamingResponse>;
  if (conversationId === "default" && opts.agentId) {
    const cachedConvId = defaultConvIdCache.get(opts.agentId);
    if (cachedConvId) {
      const bodyForCached = buildConversationMessagesCreateRequestBody(
        cachedConvId,
        messages,
        opts,
        clientTools,
      );
      stream = await client.conversations.messages.create(
        cachedConvId,
        bodyForCached,
        requestOptionsWithHeaders,
      );
    } else {
      try {
        stream = await client.conversations.messages.create(
          "default",
          requestBody,
          requestOptionsWithHeaders,
        );
      } catch (e: unknown) {
        if (process.env.DEBUG) {
          console.log(
            `[DEBUG] "default" rejected, creating real conversation for agent ${opts.agentId}`,
          );
        }
        // Both "default" and agentId path params fail on older servers.
        // Create a real conversation and cache it.
        const conv = await client.conversations.create({
          agent_id: opts.agentId,
        });
        defaultConvIdCache.set(opts.agentId, conv.id);
        const bodyForNew = buildConversationMessagesCreateRequestBody(
          conv.id,
          messages,
          opts,
          clientTools,
        );
        stream = await client.conversations.messages.create(
          conv.id,
          bodyForNew,
          requestOptionsWithHeaders,
        );
      }
    }
  } else {
    stream = await client.conversations.messages.create(
      resolvedConversationId,
      requestBody,
      requestOptionsWithHeaders,
    );
  }

  if (requestStartTime !== undefined) {
    streamRequestStartTimes.set(stream as object, requestStartTime);
  }
  streamToolContextIds.set(stream as object, contextId);
  streamRequestContexts.set(stream as object, {
    conversationId,
    resolvedConversationId,
    agentId: opts.agentId ?? null,
    requestStartedAtMs,
    otid: firstOtid,
  });

  return stream;
}
