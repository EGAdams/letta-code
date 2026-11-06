import { worstLevel } from "../../levels/level-rank.js";
import { statusLevel } from "../../levels/status-level.js";
import { MonitorSnapshot } from "../monitor-snapshot.js";
import { withStale } from "./parse-helpers.js";

/** /api/chatgpt-provider-account-status → provider and local OAuth token LEDs. */
export function parseChatgptAccount(payload) {
  const items = [
    {
      label: "provider token",
      text: payload.provider_token_state,
      level: statusLevel(payload.provider_token_state),
    },
    {
      label: "local token",
      text: payload.local_token_state,
      level: statusLevel(payload.local_token_state),
    },
  ];
  if (payload.sync_recommended)
    items.push({ label: "sync", text: "recommended", level: "warn" });
  return new MonitorSnapshot({
    level: worstLevel(items.map((i) => i.level)),
    detail: withStale(
      payload,
      payload.token_status_detail || payload.active_email || "",
    ),
    items,
  });
}
