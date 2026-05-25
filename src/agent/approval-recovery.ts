/**
 * Approval recovery helpers.
 *
 * Pure policy logic lives in `./turn-recovery-policy.ts` and is re-exported
 * here for backward compatibility. This module keeps only the async/side-effect
 * helper (`fetchRunErrorDetail`) that requires network access.
 */

import { getClient } from "./client";

export type {
  PendingApprovalInfo,
  PreStreamConflictKind,
  PreStreamErrorAction,
  PreStreamErrorOptions,
  RetryDelayCategory,
} from "./turn-recovery-policy";
// ── Re-export pure policy helpers (single source of truth) ──────────
export {
  classifyPreStreamConflict,
  extractConflictDetail,
  getPreStreamErrorAction,
  getRetryDelayMs,
  getTransientRetryDelayMs,
  isApprovalPendingError,
  isConversationBusyError,
  isEmptyResponseError,
  isEmptyResponseRetryable,
  isInvalidToolCallIdsError,
  isNonRetryableProviderErrorDetail,
  isNoPendingApprovalResponseError,
  isQuotaLimitErrorDetail,
  isRetryableProviderErrorDetail,
  parseRetryAfterHeaderMs,
  rebuildInputWithFreshDenials,
  shouldAttemptApprovalRecovery,
  shouldRetryPreStreamTransientError,
  shouldRetryRunMetadataError,
} from "./turn-recovery-policy";

// ── Async helpers (network side effects — stay here) ────────────────

type RunErrorMetadata =
  | {
      error_type?: string;
      message?: string;
      detail?: string;
      error?: { error_type?: string; message?: string; detail?: string };
    }
  | undefined
  | null;

const RUN_RETRIEVE_TIMEOUT_MS = 5000;

async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
): Promise<T> {
  return await Promise.race([
    promise,
    new Promise<T>((_resolve, reject) => {
      setTimeout(() => {
        reject(new Error(`Timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    }),
  ]);
}

export async function fetchRunErrorDetail(
  runId: string | null | undefined,
): Promise<string | null> {
  if (!runId) return null;
  try {
    const client = await getClient();
    const run = await withTimeout(
      client.runs.retrieve(runId),
      RUN_RETRIEVE_TIMEOUT_MS,
    );
    const metaError = run.metadata?.error as RunErrorMetadata;

    return (
      metaError?.detail ??
      metaError?.message ??
      metaError?.error?.detail ??
      metaError?.error?.message ??
      null
    );
  } catch {
    return null;
  }
}
