// startup-checks.js — the boot-time preload behind the startup overlay.
//
// Four independent tasks (server registry, SSH registry, server health, SSH
// health) each report into the startup gate and each fail closed: a task that
// times out or errors marks its own tab red and lets the overlay finish rather
// than hanging the dashboard behind a spinner.

const TASK_TIMEOUT = 10000; // 10-second timeout per task

export function createStartupChecks({
  doc = document,
  http,
  nav,
  tabFactory,
  startupGate,
  SM,
  SSHM,
}) {
  const runTask = async (key, work, formatSuccess, onError = null) => {
    try {
      const result = await Promise.race([
        work(),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error(`Task timeout after ${TASK_TIMEOUT}ms`)),
            TASK_TIMEOUT,
          ),
        ),
      ]);
      startupGate.complete(key, formatSuccess(result));
      return result;
    } catch (error) {
      if (typeof onError === "function") onError(error);
      startupGate.fail(key, error);
      return null;
    }
  };

  // A failed health probe must still colour its tab — silence would read as
  // "healthy".
  const markTabDown = (id) => () => {
    const tab = doc.getElementById(id);
    tab?.classList.remove("server-up", "server-starting");
    tab?.classList.add("server-down");
  };

  // Rebuild a sidebar's injected tabs from a freshly-loaded registry, then
  // re-notify the monitor so the new tabs get their colours immediately.
  const rebuildTabs = (navEl, selector, rows, build, monitor, queueLabel) => {
    for (const row of rows) {
      startupGate.writeLine(`${queueLabel}: ${row.name}`);
    }
    navEl.querySelectorAll(selector).forEach((tab) => {
      tab.remove();
    });
    for (const row of rows) navEl.appendChild(build(row));
    monitor.notify();
  };

  return async function preloadStartupChecks() {
    startupGate.start();

    const serverRegistryPromise = runTask(
      "server-registry",
      async () => {
        if (SM.servers) return SM.servers;
        SM.servers = await http.getJSON("/api/servers");
        return SM.servers;
      },
      (servers) =>
        `Loaded ${servers?.length || 0} server definition${servers?.length === 1 ? "" : "s"}.`,
    );

    const sshRegistryPromise = runTask(
      "ssh-registry",
      async () => {
        if (SSHM.connections) return SSHM.connections;
        SSHM.connections = await http.getJSON("/api/ssh-connections");
        return SSHM.connections;
      },
      (connections) =>
        `Loaded ${connections?.length || 0} SSH connection${connections?.length === 1 ? "" : "s"}.`,
    );

    const serverHealthPromise = runTask(
      "server-health",
      async () => {
        startupGate.writeLine("Calling /api/server-health...");
        SM.health.health = await SM.health.fetchHealth();
        startupGate.writeLine("Got response from /api/server-health");
        SM.health.notify();
        return SM.health.health;
      },
      (health) => {
        const rows = health?.servers || [];
        const count = rows.length;
        const nameByKey = new Map(
          (SM.servers || []).map((server) => [server.key, server.name]),
        );
        for (const server of rows) {
          startupGate.writeLine(
            `Server ${nameByKey.get(server.key) || server.key}: ${server.status || "unknown"}`,
          );
        }
        const down =
          rows.filter((server) => server.status !== "up").length || 0;
        return `Server health check finished: ${count - down}/${count} up.`;
      },
      markTabDown("btn-server-mgmt"),
    );

    const sshHealthPromise = runTask(
      "ssh-health",
      async () => {
        startupGate.writeLine("Calling /api/ssh-connection-health...");
        SSHM.health.health = await SSHM.health.fetchHealth();
        startupGate.writeLine("Got response from /api/ssh-connection-health");
        SSHM.health.notify();
        return SSHM.health.health;
      },
      (health) => {
        const rows = health?.connections || [];
        const count = rows.length;
        const nameByKey = new Map(
          (SSHM.connections || []).map((conn) => [conn.key, conn.name]),
        );
        for (const conn of rows) {
          startupGate.writeLine(
            `SSH ${nameByKey.get(conn.key) || conn.key}: ${conn.status || "unknown"}`,
          );
        }
        const down =
          rows.filter((connection) => connection.status !== "up").length || 0;
        return `SSH health check finished: ${count - down}/${count} reachable.`;
      },
      markTabDown("btn-ssh-connections"),
    );

    await Promise.all([
      serverRegistryPromise,
      sshRegistryPromise,
      serverHealthPromise,
      sshHealthPromise,
    ]);

    if (SM.servers) {
      rebuildTabs(
        nav.servers,
        "[data-server-key]",
        SM.servers,
        (s) => tabFactory.buildServerTab(s),
        SM.health,
        "Queueing server check",
      );
    }

    if (SSHM.connections) {
      rebuildTabs(
        nav.ssh,
        "[data-conn-key]",
        SSHM.connections,
        (c) => tabFactory.buildConnectionTab(c),
        SSHM.health,
        "Queueing SSH check",
      );
    }

    SM.healthPollTimer = setInterval(() => SM.pollHealth(), 10000);
    SSHM.healthPollTimer = setInterval(() => SSHM.pollHealth(), 15000);
  };
}
