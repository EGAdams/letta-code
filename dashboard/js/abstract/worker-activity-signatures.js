// Stable signatures for independently rendered Worker Activity sections.
/** Signature of what the SVG/table/legend draw: not heartbeat timestamps. */
export function taskSignature(payload) {
  return JSON.stringify({
    a: payload?.tasks_available,
    e: payload?.tasks_error,
    f: payload?.fetch_error,
    t: payload?.tasks,
    p: payload?.provider_selection,
    w: payload?.worker?.status,
  });
}

export function healthSignature(payload) {
  const w = payload?.worker || {};
  return JSON.stringify([
    payload?.ok,
    payload?.fetch_error,
    w.status,
    w.reason,
    w.service?.active,
  ]);
}

export function terminalSignature(payload) {
  return JSON.stringify([payload?.tasks, payload?.activity_events]);
}
