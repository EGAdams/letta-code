// System Status > Service Management. Poll independently of the monitored API.
import {
  renderServiceDetail,
  serviceStatusClass,
} from "../abstract/service-management-render.js";

export function createServiceManagement({
  doc = document,
  win = window,
  http,
  nav,
  viewNav,
}) {
  const parent = doc.getElementById("btn-service-mgmt");
  const body = doc.getElementById("service-management-body");
  const tabs = doc.getElementById("service-management-tabs");
  const buttons = new Map();
  let selected = null;
  let last = { services: [] };
  let busy = false;

  function paint(tab, status) {
    if (!tab) return;
    tab.classList.remove("server-up", "server-down", "server-concern");
    tab.classList.add(serviceStatusClass(status));
    tab.classList.toggle("tab-alert-red", status === "down");
    tab.classList.toggle("tab-alert", status !== "up" && status !== "down");
  }

  function render() {
    const services = last.services || [];
    if (!services.some((service) => service.key === selected))
      selected = services[0]?.key;
    for (const [key, button] of buttons) {
      if (!services.some((service) => service.key === key)) {
        button.remove();
        buttons.delete(key);
      }
    }
    for (const service of services) {
      let button = buttons.get(service.key);
      if (!button) {
        button = doc.createElement("button");
        button.type = "button";
        button.className = "tab";
        button.dataset.service = service.key;
        button.addEventListener("click", () => {
          selected = service.key;
          render();
        });
        tabs?.appendChild(button);
        buttons.set(service.key, button);
      }
      button.textContent = service.label;
      button.classList.toggle("active", service.key === selected);
      button.setAttribute("aria-pressed", String(service.key === selected));
      paint(button, service.status);
    }
    paint(parent, last.status);
    viewNav.updateSystemStatusTab();
    if (body)
      body.innerHTML = renderServiceDetail(
        services.find((service) => service.key === selected),
        last,
      );
  }

  async function poll() {
    if (busy) return;
    busy = true;
    try {
      const payload = await http.getJSON("/api/service-management");
      const statuses = ["up", "down", "concern", "unknown"];
      if (
        !Array.isArray(payload.services) ||
        !payload.services.length ||
        !statuses.includes(payload.status) ||
        !payload.services.every(
          (service) =>
            service &&
            typeof service.key === "string" &&
            typeof service.unit === "string" &&
            typeof service.label === "string" &&
            statuses.includes(service.status),
        )
      )
        throw new Error("No service observations were returned.");
      last = payload;
    } catch (error) {
      // Never keep green tabs or growing downtime based on stale observations.
      last = {
        ...last,
        status: "unknown",
        fetch_error: `Service check unavailable: ${error.message}`,
        services: last.services.map((service) => ({
          ...service,
          status: "unknown",
          active: "unknown",
          sub: "",
          down_for_seconds: null,
          detail:
            "Current state cannot be verified. Fields and history below are from the last successful check.",
        })),
      };
    } finally {
      busy = false;
      render();
    }
  }

  doc
    .getElementById("service-management-refresh")
    ?.addEventListener("click", () => void poll());
  doc.getElementById("btn-back-services")?.addEventListener("click", () => {
    nav.services.classList.add("hidden");
    viewNav.returnToStatus("service-management");
  });
  doc.addEventListener?.("visibilitychange", () => {
    if (doc.visibilityState === "visible") void poll();
  });
  void poll();
  win.setInterval(() => void poll(), 15000);
  return {
    poll,
    open() {
      nav.status.classList.add("hidden");
      nav.services.classList.remove("hidden");
      viewNav.activateView("service-management");
      render();
      void poll();
    },
  };
}
