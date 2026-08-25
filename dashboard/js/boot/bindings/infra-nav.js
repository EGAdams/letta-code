// infra-nav.js — the Server Management and SSH Connections sidebars.
//
// Both tab lists are injected from their registry at boot, so both use event
// delegation, and both back out one level to System Status rather than Home.

export function bindInfraNav({ doc, nav, viewNav, SM, SSHM }) {
  nav.servers.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-servers") return;
    if (tab.dataset.serverKey) {
      viewNav.setActive(nav.servers, ".tab", tab);
      SM.openServer(
        tab.dataset.serverKey,
        tab.dataset.serverName || tab.textContent,
      );
    }
  });

  doc.getElementById("btn-back-servers")?.addEventListener("click", () => {
    SM.stopPoll();
    nav.servers.classList.add("hidden");
    viewNav.returnToStatus("server-management");
  });

  nav.ssh.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-ssh") return;
    if (tab.dataset.connKey) {
      viewNav.setActive(nav.ssh, ".tab", tab);
      SSHM.openConnection(
        tab.dataset.connKey,
        tab.dataset.connName || tab.textContent,
      );
    }
  });

  doc.getElementById("btn-back-ssh")?.addEventListener("click", () => {
    SSHM.stopPoll();
    nav.ssh.classList.add("hidden");
    viewNav.returnToStatus("ssh-connections");
  });
}
