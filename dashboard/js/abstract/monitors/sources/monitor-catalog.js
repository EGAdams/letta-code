import { parseAgentActivity } from "./parsers/agent-activity-parser.js";
import { parseAgentHealth } from "./parsers/agent-health-parser.js";
import { parseBridgePoll } from "./parsers/bridge-poll-parser.js";
import { parseChatgptAccount } from "./parsers/chatgpt-account-parser.js";
import { parseCodeStatus } from "./parsers/code-status-parser.js";
import { parseCodexSync } from "./parsers/codex-sync-parser.js";
import { parseGatewayRequests } from "./parsers/gateway-requests-parser.js";
import { parseIntakeHalt } from "./parsers/intake-halt-parser.js";
import { parseModelStats } from "./parsers/model-stats-parser.js";
import { parsePcMetrics } from "./parsers/pc-metrics-parser.js";
import { parsePrinter } from "./parsers/printer-parser.js";
import { parseReceptionistAlerts } from "./parsers/receptionist-alerts-parser.js";
import { parseScannerIntake } from "./parsers/scanner-intake-parser.js";
import { parseServerHealth } from "./parsers/server-health-parser.js";
import { parseSshHealth } from "./parsers/ssh-health-parser.js";
import { parseTokenRate } from "./parsers/token-rate-parser.js";
import { parseWorkerActivity } from "./parsers/worker-activity-parser.js";
import { parseWslInterop } from "./parsers/wsl-interop-parser.js";

/**
 * Every monitor on the All Monitors page, as data. A new monitor is a new
 * row (plus its parser) — nothing else changes. `view` names the card body
 * component; `gauge` names a GaugeFactory type when view is "gauge".
 * `presets` puts push buttons under the body that pick which item it shows;
 * `preset` is the one pressed at load (SSD: disk space is the live worry).
 */
const PC_PRESETS = Object.freeze([
  { key: "ram", label: "RAM" },
  { key: "disk", label: "SSD" },
  { key: "net", label: "NETWORK" },
  { key: "max", label: "MAX" },
]);
const pc = (key, label) => ({
  key: `pc-${key}`,
  group: "Machines",
  label,
  url: `/api/pc-metrics?pc=${key}`,
  view: "gauge",
  gauge: "PercentUsedGauge",
  presets: PC_PRESETS,
  preset: "disk",
  parse: parsePcMetrics,
});
const quota = (key, label) => ({
  key: `quota-${key}`,
  group: "Model quotas",
  label,
  url: `/api/model-stats?source=${key}`,
  view: "gauge",
  gauge: "QuotaLeftGauge",
  parse: parseModelStats,
});

export const MONITOR_CATALOG = Object.freeze([
  pc("win11", "Win11"),
  pc("win10", "Win10"),
  pc("moms46", "Moms46"),
  {
    key: "servers",
    group: "Services",
    label: "Servers",
    url: "/api/server-health",
    view: "gauge",
    gauge: "HealthyRatioGauge",
    parse: parseServerHealth,
  },
  {
    key: "ssh",
    group: "Services",
    label: "SSH connections",
    url: "/api/ssh-connection-health",
    view: "donut",
    parse: parseSshHealth,
  },
  {
    key: "wsl",
    group: "Services",
    label: "WSL interop",
    url: "/api/wsl-interop",
    view: "list",
    parse: parseWslInterop,
  },
  {
    key: "code",
    group: "Services",
    label: "Dashboard code",
    url: "/api/code-status",
    view: "list",
    parse: parseCodeStatus,
  },
  {
    key: "alerts",
    group: "Agents",
    label: "Receptionist alerts",
    url: "/api/receptionist-alerts",
    view: "gauge",
    gauge: "AlertCountGauge",
    parse: parseReceptionistAlerts,
  },
  {
    key: "agent-health",
    group: "Agents",
    label: "Agent health",
    url: "/api/agent-health",
    view: "gauge",
    gauge: "HealthyRatioGauge",
    parse: parseAgentHealth,
  },
  {
    key: "agent-activity",
    group: "Agents",
    label: "Agent activity",
    url: "/api/agent-activity",
    view: "donut",
    parse: parseAgentActivity,
  },
  {
    key: "token-rate",
    group: "Agents",
    label: "Claude SDK tokens",
    url: "/api/claude-sdk-token-rate",
    view: "sparkline",
    parse: parseTokenRate,
  },
  {
    key: "bridge-poll",
    group: "Bridge",
    label: "Bridge worker poll",
    url: "/api/agent-bridge-poll",
    view: "ring",
    parse: (p) => parseBridgePoll(p),
  },
  {
    key: "worker-activity",
    group: "Bridge",
    label: "Worker activity",
    url: "/api/worker-activity",
    view: "donut",
    parse: parseWorkerActivity,
  },
  {
    key: "gateway-requests",
    group: "Bridge",
    label: "Supervised requests",
    url: "/api/worker-activity",
    view: "list",
    parse: parseGatewayRequests,
  },
  quota("w11-claude", "eg1972 claude"),
  quota("w11-codex", "eg1972 codex"),
  quota("r46-claude", "rbarnesrol claude"),
  quota("r46-codex", "rbarnesrol codex"),
  quota("gemini", "Gemini Flash"),
  {
    key: "chatgpt",
    group: "Model quotas",
    label: "ChatGPT OAuth",
    url: "/api/chatgpt-provider-account-status",
    view: "list",
    parse: parseChatgptAccount,
  },
  {
    key: "codex-sync",
    group: "Model quotas",
    label: "Codex OAuth sync",
    url: "/api/codex-sync-status",
    view: "ring",
    parse: parseCodexSync,
  },
  {
    key: "printer",
    group: "Documents",
    label: "Printer",
    url: "/api/printer",
    view: "list",
    parse: parsePrinter,
  },
  {
    key: "scanner-intake",
    group: "Documents",
    label: "Scanner intake",
    url: "/api/scanner-intake-status",
    view: "list",
    parse: parseScannerIntake,
  },
  {
    key: "intake-halt",
    group: "Documents",
    label: "Intake halt",
    url: "/api/intake-halt",
    view: "list",
    parse: parseIntakeHalt,
  },
]);
