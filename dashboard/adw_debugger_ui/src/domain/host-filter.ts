import type { RunState } from "./state";

// There is currently no registered machine identity for Dad in this checkout.
// Keep this registry empty until an authoritative machine ID/hostname is
// enrolled.  A producer label, agent name, IP guess, or dashboard hostname is
// not sufficient evidence and must never make another machine's run appear.
const REGISTERED_DADS_HOSTS = new Set<string>();

export function isDadsComputer(run: RunState): boolean {
  return (
    run.executionHost !== null &&
    REGISTERED_DADS_HOSTS.has(run.executionHost.trim().toLowerCase())
  );
}

export function hasKnownExecutionHost(run: RunState): boolean {
  return Boolean(run.executionHost?.trim());
}
