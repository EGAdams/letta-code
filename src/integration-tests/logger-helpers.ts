const LOCAL_API =
  process.env.LETTA_LOGGER_RESET_API ??
  "https://americansjewelry.com/libraries/local-php-api/index.php";

const RESET_TIMEOUT_MS = Number(
  process.env.LETTA_LOGGER_RESET_TIMEOUT_MS ?? "15000",
);
const RESET_CONCURRENCY = Number(
  process.env.LETTA_LOGGER_RESET_CONCURRENCY ?? "4",
);
const RESET_DISABLED = process.env.LETTA_LOGGER_RESET_DISABLED === "1";
const DEFAULT_VIEWER_BASE =
  process.env.LETTA_LOGGER_VIEWER_BASE ?? "http://localhost:8080";
export const ALL_LOGGER_IDS = [
  "ErrorFormat_ResultSubtype_2026",
  "ErrorFormat_StopReason_2026",
  "ErrorFormat_ApiError_2026",
  "ErrorFormat_ErrorSubtypeCheck_2026",
  "ErrorFormat_ConflictDetail_2026",
  "ErrorFormat_ApprovalDetail_2026",
  "HeadlessInput_InitControl_2026",
  "HeadlessInput_UserMessage_2026",
  "HeadlessInput_MultiTurn_2026",
  "HeadlessInput_Interrupt_2026",
  "HeadlessInput_RecoverApprovals_2026",
  "HeadlessInput_RecoverMismatch_2026",
  "HeadlessInput_PartialMessages_2026",
  "HeadlessInput_UnknownControl_2026",
  "HeadlessInput_InvalidJson_2026",
  "HeadlessInput_TaskTool_2026",
  "StreamJson_InitMessage_2026",
  "StreamJson_SessionIdUuid_2026",
  "StreamJson_ResultFormat_2026",
  "StreamJson_PartialMessages_2026",
  "StreamJson_NoPartialMessages_2026",
  "StartupFlow_AgentNotFound_2026",
  "StartupFlow_ConvNotFound_2026",
  "StartupFlow_ImportNotFound_2026",
  "StartupFlow_NewAgent_2026",
  "StartupFlow_ValidAgent_2026",
  "StartupFlow_ValidConv_2026",
  "StartupFlow_SerializedConvId_2026",
  "StartupFlow_DefaultConv_2026",
  "StartupFlow_InitBlocksNone_2026",
  "StartupFlow_NoPrompt_2026",
  "StartupFlow_StaleConvFallback_2026",
  "LazyApproval_ConcurrentMessage_2026",
  "PrestreamApproval_Recovery_2026",
  "OAuthHealthCheck_2026",
  "ScissariTestLogger_2026",
];

export async function resetLogger(objectViewId: string): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
    console.warn(
      `[resetLogger] DELETE timed out after ${RESET_TIMEOUT_MS}ms for ${objectViewId}`,
    );
  }, RESET_TIMEOUT_MS);

  const t0 = Date.now();
  try {
    const res = await fetch(`${LOCAL_API}/object/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ object_view_id: objectViewId }),
      signal: controller.signal,
    });
    const elapsed = Date.now() - t0;
    if (!res.ok) {
      console.warn(
        `[resetLogger] DELETE ${objectViewId} → HTTP ${res.status} in ${elapsed}ms`,
      );
      return false;
    } else {
      console.log(`[resetLogger] DELETE ${objectViewId} → OK (${elapsed}ms)`);
      return true;
    }
  } catch (err) {
    const elapsed = Date.now() - t0;
    const label =
      err instanceof Error && err.name === "AbortError" ? "TIMEOUT" : "ERROR";
    console.warn(
      `[resetLogger] ${label} deleting ${objectViewId} after ${elapsed}ms: ${err}`,
    );
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function probeUrl(url: string, label: string): Promise<void> {
  const controller = new AbortController();
  const timeoutMs = 5000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const t0 = Date.now();
  try {
    const res = await fetch(url, { signal: controller.signal });
    const elapsed = Date.now() - t0;
    console.warn(
      `[resetAllLoggers:probe] ${label}: HTTP ${res.status} ${res.statusText} in ${elapsed}ms (${url})`,
    );
  } catch (err) {
    const elapsed = Date.now() - t0;
    const detail =
      err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    console.warn(
      `[resetAllLoggers:probe] ${label}: FAILED in ${elapsed}ms (${url}) -> ${detail}`,
    );
  } finally {
    clearTimeout(timer);
  }
}

async function diagnoseLoggerTransport(): Promise<void> {
  console.warn("[resetAllLoggers] Running logger transport diagnostics...");
  const viewerBase = DEFAULT_VIEWER_BASE.replace(/\/$/, "");
  await probeUrl(`${viewerBase}/`, "viewer-shell");
  await probeUrl(
    `${LOCAL_API}/object/select?object_view_id=${encodeURIComponent(ALL_LOGGER_IDS[0] ?? "")}`,
    "upstream-api",
  );
}

export async function resetAllLoggers(): Promise<void> {
  if (RESET_DISABLED) {
    console.log(
      "[resetAllLoggers] Skipped because LETTA_LOGGER_RESET_DISABLED=1",
    );
    return;
  }
  console.log(
    `[resetAllLoggers] Starting reset of ${ALL_LOGGER_IDS.length} loggers on ${LOCAL_API} ` +
      `(timeout=${RESET_TIMEOUT_MS}ms, concurrency=${RESET_CONCURRENCY}) …`,
  );

  const t0 = Date.now();
  let failureCount = 0;
  for (let i = 0; i < ALL_LOGGER_IDS.length; i += RESET_CONCURRENCY) {
    const batch = ALL_LOGGER_IDS.slice(i, i + RESET_CONCURRENCY);
    await Promise.all(
      batch.map(async (id) => {
        const ok = await resetLogger(id);
        if (!ok) {
          failureCount += 1;
        }
      }),
    );
  }
  console.log(`[resetAllLoggers] Done in ${Date.now() - t0}ms`);
  if (failureCount > 0) {
    console.warn(
      `[resetAllLoggers] ${failureCount} logger reset(s) failed. Collecting endpoint diagnostics.`,
    );
    await diagnoseLoggerTransport();
  }
}
