import { settingsManager } from "../../settings-manager";

const CLOUD_API_BASE = "https://api.letta.com";
const CLOUD_APP_BASE = "https://app.letta.com";

function getConfiguredServerUrl(): string {
  try {
    const settings = settingsManager.getSettings();
    return (
      process.env.LETTA_BASE_URL ||
      settings.env?.LETTA_BASE_URL ||
      CLOUD_API_BASE
    );
  } catch {
    return process.env.LETTA_BASE_URL || CLOUD_API_BASE;
  }
}

export function getAppBaseUrl(serverUrl = getConfiguredServerUrl()): string {
  const normalized = serverUrl.replace(/\/+$/, "").replace(/\/v1$/, "");

  if (normalized === CLOUD_API_BASE || normalized === "https://api.letta.com") {
    return CLOUD_APP_BASE;
  }

  return normalized;
}

/**
 * Build a chat URL for an agent, with optional conversation and extra query params.
 */
export function buildChatUrl(
  agentId: string,
  options?: {
    conversationId?: string;
    view?: string;
    deviceId?: string;
  },
): string {
  const base = `${getAppBaseUrl()}/chat/${agentId}`;
  const params = new URLSearchParams();

  if (options?.view) {
    params.set("view", options.view);
  }
  if (options?.deviceId) {
    params.set("deviceId", options.deviceId);
  }
  if (options?.conversationId && options.conversationId !== "default") {
    params.set("conversation", options.conversationId);
  }

  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

/**
 * Build a non-agent app URL (e.g. settings pages).
 */
export function buildAppUrl(path: string): string {
  return `${getAppBaseUrl()}${path}`;
}
