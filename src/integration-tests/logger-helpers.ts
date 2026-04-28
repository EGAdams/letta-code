// In Bun tests, use the direct API by default to avoid coupling cleanup to the viewer proxy.
// Override with LETTA_LOGGER_RESET_API if needed (for example http://localhost:8080/php-api).
const LOCAL_API =
  process.env.LETTA_LOGGER_RESET_API ??
  "https://americansjewelry.com/libraries/local-php-api/index.php";

const RESET_TIMEOUT_MS = Number(process.env.LETTA_LOGGER_RESET_TIMEOUT_MS ?? "15000");
const RESET_CONCURRENCY = Number(process.env.LETTA_LOGGER_RESET_CONCURRENCY ?? "4");

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
  "StartupFlow_DefaultConv_2026",
  "StartupFlow_InitBlocksNone_2026",
  "LazyApproval_ConcurrentMessage_2026",
  "PrestreamApproval_Recovery_2026",
  "OAuthHealthCheck_2026",
  "ScissariTestLogger_2026",
];


export async function resetLogger(objectViewId: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
    console.warn(`[resetLogger] DELETE timed out after ${RESET_TIMEOUT_MS}ms for ${objectViewId}`);
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
      console.warn(`[resetLogger] DELETE ${objectViewId} → HTTP ${res.status} in ${elapsed}ms`);
    } else {
      console.log(`[resetLogger] DELETE ${objectViewId} → OK (${elapsed}ms)`);
    }
  } catch (err) {
    const elapsed = Date.now() - t0;
    const label = (err instanceof Error && err.name === "AbortError") ? "TIMEOUT" : "ERROR";
    console.warn(`[resetLogger] ${label} deleting ${objectViewId} after ${elapsed}ms: ${err}`);
  } finally {
    clearTimeout(timer);
  }
}

export async function resetAllLoggers(): Promise<void> {
  console.log(
    `[resetAllLoggers] Starting reset of ${ALL_LOGGER_IDS.length} loggers on ${LOCAL_API} ` +
    `(timeout=${RESET_TIMEOUT_MS}ms, concurrency=${RESET_CONCURRENCY}) …`,
  );
  const t0 = Date.now();
  for (let i = 0; i < ALL_LOGGER_IDS.length; i += RESET_CONCURRENCY) {
    const batch = ALL_LOGGER_IDS.slice(i, i + RESET_CONCURRENCY);
    await Promise.all(batch.map(resetLogger));
  }
  console.log(`[resetAllLoggers] Done in ${Date.now() - t0}ms`);
}
