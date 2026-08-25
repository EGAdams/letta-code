// gates.js — the two concrete startup gates, built from the shared
// createStartupGate() Template Method (js/abstract/startup-gate.js).

import { createStartupGate } from "../abstract/startup-gate.js";

export function createGates({ doc, win, elements }) {
  const startupGate = createStartupGate({
    doc,
    win,
    elements,
    tasks: [
      {
        key: "server-registry",
        label: "Loading server registry",
        detail: "Fetching server definitions for Server Management tabs",
      },
      {
        key: "server-health",
        label: "Checking server health",
        detail: "Running initial Server Management health check",
      },
      {
        key: "ssh-registry",
        label: "Loading SSH connections",
        detail: "Fetching SSH connection definitions",
      },
      {
        key: "ssh-health",
        label: "Checking SSH connectivity",
        detail: "Running initial SSH connection health check",
      },
    ],
    labels: {
      running: "Running Dashboard checks...",
      starting: "Checking server and SSH connections...",
      advancing: "Advancing startup checks",
      finished: "Finished system check.",
      finishedLine: "finished system check.",
    },
  });

  // Reopened every time Agent Management loads its roster, so it resets.
  const agentGate = createStartupGate({
    doc,
    win,
    elements,
    resettable: true,
    tasks: [
      {
        key: "agents",
        label: "Loading agents",
        detail: "Fetching agent definitions",
      },
    ],
    labels: {
      running: "Running Agent Management checks...",
      starting: "Checking agent roster...",
      advancing: "Advancing agent checks",
      finished: "Finished loading agents.",
      finishedLine: "finished loading agents.",
    },
  });

  return { startupGate, agentGate };
}
