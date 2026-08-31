import * as fs from "node:fs";
import * as path from "node:path";
import * as url from "node:url";

export async function relay_message_to_chatgpt(
  message: string,
  browser_server_url: string = "",
  executor_url: string = "",
  executor_token: string = "",
  timeout_seconds: number = 180,
  poll_seconds: number = 10,
  stability_checks: number = 2,
  max_total_seconds: number = 600,
): Promise<string> {
  /**
   * Send a message to the controlled ChatGPT browser and return ChatGPT's reply.
   *
   * The tool uses the local browser server API documented in API_GUIDE.md:
   * it posts to /type, posts to /send, then polls /read_thread until the
   * latest assistant reply appears stable.
   */

  function normalizeBaseUrl(rawUrl: string): string {
    return rawUrl.replace(/\/$/, "");
  }

  async function requestJson(
    baseUrl: string,
    method: string,
    path: string,
    payload: object | null = null,
    timeout: number = 20,
  ): Promise<Record<string, unknown>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

    try {
      const options: RequestInit = {
        method,
        signal: controller.signal,
        headers: {},
      };

      if (payload) {
        options.headers = {
          ...options.headers,
          "Content-Type": "application/json",
        };
        options.body = JSON.stringify(payload);
      }

      const response = await fetch(
        `${normalizeBaseUrl(baseUrl)}${path}`,
        options,
      );
      const text = await response.text();
      return text ? JSON.parse(text) : {};
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function executorCandidates(): string[] {
    const candidates = [
      executor_url,
      process.env.EXECUTOR_URL || "",
      "http://100.72.158.63:8787",
      "http://10.0.0.7:8787",
      "http://100.80.49.10:8787",
    ];
    const seen = new Set<string>();
    const urls: string[] = [];

    for (const candidate of candidates) {
      if (!candidate) continue;
      const normalized = normalizeBaseUrl(candidate);
      if (!seen.has(normalized)) {
        seen.add(normalized);
        urls.push(normalized);
      }
    }

    return urls;
  }

  async function resolveExecutor(): Promise<[string, string] | null> {
    const token =
      executor_token ||
      process.env.EXECUTOR_TOKEN ||
      "fd023ff5be687a9ff5486fa7321aa4a4c1dcf0040b7fc34d";

    const errors: string[] = [];

    for (const candidate of executorCandidates()) {
      try {
        const health = await requestJson(candidate, "GET", "/health", null, 5);
        if (health.ok === true) {
          return [candidate, token];
        }
        errors.push(
          `${candidate}: unhealthy response ${JSON.stringify(health)}`,
        );
      } catch (e) {
        errors.push(
          `${candidate}: ${e instanceof Error ? e.message : String(e)}`,
        );
      }
    }

    return null;
  }

  async function runViaExecutor(
    executor: [string, string],
    command: string,
    timeout: number = 30,
  ): Promise<string> {
    const [base, token] = executor;
    const payload = { command, cwd: ".", timeout_sec: timeout };

    const options: RequestInit = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    };

    if (token) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      };
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      (timeout + 10) * 1000,
    );

    try {
      const response = await fetch(`${normalizeBaseUrl(base)}/run`, {
        ...options,
        signal: controller.signal,
      });
      const result = (await response.json()) as Record<string, unknown>;

      if (Number(result.returncode || 1) !== 0) {
        throw new Error(
          `executor curl failed: ${String(result.stderr || result.stdout || result)}`,
        );
      }
      return String(result.stdout || "");
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function requestJsonViaExecutor(
    executor: [string, string],
    browserBaseUrl: string,
    method: string,
    path: string,
    payload: object | null = null,
    timeout: number = 30,
  ): Promise<Record<string, unknown>> {
    const baseUrl = normalizeBaseUrl(browserBaseUrl);
    const url = `${baseUrl}${path}`;

    const parts = [
      "curl",
      "-sS",
      "--max-time",
      String(Math.max(1, timeout)),
      "-X",
      method,
      url,
    ];

    if (payload) {
      parts.push("-H", "Content-Type: application/json");
      parts.push("--data-raw", JSON.stringify(payload));
    }

    const command = parts.map((p) => `'${p.replace(/'/g, "'\\''")}'`).join(" ");
    const raw = await runViaExecutor(executor, command, timeout);
    return raw ? JSON.parse(raw) : {};
  }

  function candidateBrowserUrls(): string[] {
    const candidates = [
      browser_server_url,
      process.env.BROWSER_SERVER_URL || "",
      "http://127.0.0.1:5001",
      "http://localhost:5001",
      "http://host.docker.internal:5001",
      "http://100.80.49.10:5001",
    ];
    const seen = new Set<string>();
    const urls: string[] = [];

    for (const candidate of candidates) {
      if (!candidate) continue;
      const normalized = normalizeBaseUrl(candidate);
      if (!seen.has(normalized)) {
        seen.add(normalized);
        urls.push(normalized);
      }
    }

    return urls;
  }

  async function resolveBrowserServerUrl(
    executor: [string, string] | null = null,
  ): Promise<string> {
    const errors: string[] = [];

    for (const candidate of candidateBrowserUrls()) {
      try {
        let health: Record<string, unknown>;

        if (executor) {
          health = await requestJsonViaExecutor(
            executor,
            candidate,
            "GET",
            "/health",
            null,
            5,
          );
        } else {
          health = await requestJson(candidate, "GET", "/health", null, 5);
        }

        if (health.status === "ok") {
          return candidate;
        }
        errors.push(
          `${candidate}: unhealthy response ${JSON.stringify(health)}`,
        );
      } catch (e) {
        errors.push(
          `${candidate}: ${e instanceof Error ? e.message : String(e)}`,
        );
      }
    }

    throw new Error(
      `No reachable browser server. Tried: ${errors.join(" | ")}`,
    );
  }

  const startBrowserServerCommand =
    "cd ~/letta-code/browser_tools && " +
    "kill $(cat /tmp/browser_server.pid 2>/dev/null) 2>/dev/null; sleep 1; " +
    "source .venv/bin/activate 2>/dev/null && " +
    "BROWSER_SERVER_HOST=0.0.0.0 nohup python3 browser_server.py >/tmp/browser_server.log 2>&1 & " +
    "echo $! > /tmp/browser_server.pid";

  async function startBrowserServer(executor: [string, string]): Promise<void> {
    const sshCommand =
      "ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new " +
      `adamsl@100.80.49.10 '${startBrowserServerCommand}'`;
    await runViaExecutor(executor, sshCommand, 30);
  }

  async function notifyLoginNeeded(executor: [string, string]): Promise<void> {
    const sshCommand =
      "ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new " +
      "adamsl@100.80.49.10 'bash ~/server_tools/notify_chatgpt_login_needed.sh'";
    try {
      await runViaExecutor(executor, sshCommand, 15);
    } catch {
      // best-effort notification only
    }
  }

  async function startAndWaitForBrowserServer(
    executor: [string, string],
    waitSeconds: number = 30,
    pollInterval: number = 3,
  ): Promise<string | null> {
    try {
      await startBrowserServer(executor);
    } catch {
      return null;
    }

    const deadline = Date.now() + Math.max(1, waitSeconds) * 1000;
    while (Date.now() < deadline) {
      await new Promise((resolve) =>
        setTimeout(resolve, Math.max(1, pollInterval) * 1000),
      );
      for (const candidate of candidateBrowserUrls()) {
        try {
          const health = await requestJsonViaExecutor(
            executor,
            candidate,
            "GET",
            "/health",
            null,
            5,
          );
          if (health.status === "ok") {
            return candidate;
          }
        } catch {}
      }
    }
    return null;
  }

  function latestAssistantText(thread: Array<Record<string, unknown>>): string {
    for (let i = thread.length - 1; i >= 0; i--) {
      const turn = thread[i];
      if (turn && turn.role === "assistant" && turn.text) {
        return String(turn.text).trim();
      }
    }
    return "";
  }

  function latestAssistantTurn(
    thread: Array<Record<string, unknown>>,
  ): Record<string, unknown> | null {
    for (let i = thread.length - 1; i >= 0; i--) {
      const turn = thread[i];
      if (turn && turn.role === "assistant" && turn.text) {
        return turn;
      }
    }
    return null;
  }

  function latestUserTurn(
    thread: Array<Record<string, unknown>>,
  ): Record<string, unknown> | null {
    for (let i = thread.length - 1; i >= 0; i--) {
      const turn = thread[i];
      if (turn && turn.role === "user" && turn.text) {
        return turn;
      }
    }
    return null;
  }

  function looksLikePlaceholder(text: string): boolean {
    const normalized = text.trim().toLowerCase().replace(/\s+/g, " ");
    return [
      "",
      "thinking",
      "thinking...",
      "working",
      "working...",
      "generating",
      "generating...",
    ].includes(normalized);
  }

  const startedAt = Date.now();
  const executor = await resolveExecutor();

  let baseUrl: string;
  try {
    baseUrl = await resolveBrowserServerUrl(executor);
  } catch (e) {
    return JSON.stringify({
      status: "BROWSER_SERVER_UNREACHABLE",
      transport: executor ? "executor" : "direct",
      elapsed_seconds: ((Date.now() - startedAt) / 1000).toFixed(1),
      response: null,
      thread: [],
      turn_count: 0,
      message: e instanceof Error ? e.message : String(e),
    });
  }

  async function browserRequest(
    method: string,
    path: string,
    payload: object | null = null,
    timeout: number = 30,
  ): Promise<Record<string, unknown>> {
    if (executor) {
      return await requestJsonViaExecutor(
        executor,
        baseUrl,
        method,
        path,
        payload,
        timeout,
      );
    }
    return await requestJson(baseUrl, method, path, payload, timeout);
  }

  const before = await browserRequest("GET", "/read_thread?last=20", null, 20);
  const beforeThread = (before.thread as Array<Record<string, unknown>>) || [];
  const beforeAssistant = latestAssistantTurn(beforeThread);
  const beforeAssistantId = beforeAssistant?.turn_id as string | undefined;
  const beforeAssistantText = beforeAssistant
    ? String(beforeAssistant.text || "").trim()
    : "";
  const beforeUser = latestUserTurn(beforeThread);
  const beforeUserId = beforeUser?.turn_id as string | undefined;

  await browserRequest("POST", "/type", { text: message }, 30);
  await browserRequest("POST", "/send", null, 30);

  let deadline = Date.now() + Math.max(1, timeout_seconds) * 1000;
  const absoluteDeadline =
    Date.now() + Math.max(max_total_seconds, timeout_seconds) * 1000;
  let lastText = "";
  let stableCount = 0;
  let lastThread: Array<Record<string, unknown>> = [];

  while (Date.now() < absoluteDeadline) {
    const threadPayload = await browserRequest(
      "GET",
      "/read_thread?last=20",
      null,
      30,
    );
    lastThread = (threadPayload.thread as Array<Record<string, unknown>>) || [];
    const turnCount = Number(threadPayload.turn_count || lastThread.length);
    const currentAssistant = latestAssistantTurn(lastThread);
    const currentAssistantId = currentAssistant?.turn_id as string | undefined;
    const currentText = currentAssistant
      ? String(currentAssistant.text || "").trim()
      : "";
    const currentUser = latestUserTurn(lastThread);
    const currentUserId = currentUser?.turn_id as string | undefined;

    if (
      currentUserId &&
      currentUserId !== beforeUserId &&
      currentAssistantId &&
      (currentAssistantId !== beforeAssistantId ||
        currentText !== beforeAssistantText) &&
      currentText &&
      !looksLikePlaceholder(currentText)
    ) {
      if (currentText === lastText) {
        stableCount++;
      } else {
        lastText = currentText;
        stableCount = 1;
        deadline = Date.now() + Math.max(1, timeout_seconds) * 1000;
      }

      if (stableCount >= Math.max(1, stability_checks)) {
        return JSON.stringify({
          status: "ok",
          transport: executor ? "executor" : "direct",
          browser_server_url: baseUrl,
          elapsed_seconds: ((Date.now() - startedAt) / 1000).toFixed(1),
          response: currentText,
          thread: lastThread,
          turn_count: turnCount,
        });
      }
    }

    if (Date.now() >= deadline) {
      return JSON.stringify({
        status: "TIMEOUT_ERROR",
        transport: executor ? "executor" : "direct",
        browser_server_url: baseUrl,
        elapsed_seconds: ((Date.now() - startedAt) / 1000).toFixed(1),
        response: lastText || null,
        thread: lastThread,
        turn_count: lastThread.length,
        message: "Timed out waiting for a stable ChatGPT assistant reply.",
      });
    }

    await new Promise((resolve) =>
      setTimeout(resolve, Math.max(1, poll_seconds) * 1000),
    );
  }

  return JSON.stringify({
    status: "TIMEOUT_ERROR",
    transport: executor ? "executor" : "direct",
    browser_server_url: baseUrl,
    elapsed_seconds: ((Date.now() - startedAt) / 1000).toFixed(1),
    response: lastText || null,
    thread: lastThread,
    turn_count: lastThread.length,
    message: "Reached absolute max_total_seconds while waiting for ChatGPT.",
  });
}
