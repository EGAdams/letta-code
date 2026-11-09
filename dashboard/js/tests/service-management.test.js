import { describe, expect, test } from "bun:test";
import { renderServiceDetail } from "../abstract/service-management-render.js";
import { bindMainNav } from "../boot/bindings/main-nav.js";
import { createServiceManagement } from "../boot/service-management.js";
import { createViewNavigator } from "../boot/view-navigator.js";
import { FakeDocument } from "./_fake-dom.js";

const flush = async () => {
  for (let i = 0; i < 8; i++) await Promise.resolve();
};
const service = (key, status = "up") => ({
  key,
  label: key,
  status,
  unit: `${key}.service`,
  active: status === "up" ? "active" : "failed",
  sub: "running",
  scope: "user",
  loaded: "loaded",
  enabled: "enabled",
  checked_at: 200,
  events: [],
});

function setup() {
  const doc = new FakeDocument();
  const node = (id, type = "div") => {
    const element = doc.createElement(type);
    element.id = id;
    return element;
  };
  const nav = {
    main: node("nav-main"),
    status: node("nav-status"),
    services: node("nav-services"),
  };
  nav.services.classList.add("hidden");
  for (const id of [
    "btn-system-status",
    "service-management-body",
    "service-management-tabs",
    "service-management-refresh",
    "btn-back-services",
  ])
    node(id);
  for (const id of [
    "btn-server-mgmt",
    "btn-service-mgmt",
    "btn-ssh-connections",
    "btn-model-stats",
    "btn-pc-monitor",
    "btn-wsl-interop",
    "btn-worker-activity",
  ]) {
    const button = node(id, "button");
    button.classList.add("server-up");
    if (id === "btn-service-mgmt") {
      button.dataset.nav = "status";
      button.dataset.target = "service-management";
      nav.status.appendChild(button);
    }
  }
  for (const id of ["service-management", "status-home"])
    node(id, "section").classList.add("view");
  let payload = {
    status: "up",
    checked_at: 200,
    services: [service("api"), service("watchdog"), service("worker")],
  };
  let failure = false;
  let calls = 0;
  const timers = [];
  const viewNav = createViewNavigator({ doc, nav });
  const SVC = createServiceManagement({
    doc,
    nav,
    viewNav,
    win: { setInterval: (fn, ms) => timers.push({ fn, ms }) },
    http: {
      getJSON: async () => {
        calls++;
        if (failure) throw new Error("connection refused");
        return payload;
      },
    },
  });
  bindMainNav({ doc, nav, viewNav, SVC });
  return {
    doc,
    nav,
    SVC,
    timers,
    calls: () => calls,
    setPayload: (value) => {
      payload = value;
    },
    fail: (value) => {
      failure = value;
    },
  };
}

describe("Service Management", () => {
  test("opens child service tabs and Back returns to System Status", async () => {
    const env = setup();
    await flush();
    env.doc.getElementById("btn-service-mgmt").click();
    expect(env.nav.status.classList.contains("hidden")).toBe(true);
    expect(env.nav.services.classList.contains("hidden")).toBe(false);
    expect(
      env.doc.getElementById("service-management").classList.contains("active"),
    ).toBe(true);
    const worker = env.doc
      .getElementById("service-management-tabs")
      .querySelector('[data-service="worker"]');
    worker.click();
    expect(worker.classList.contains("active")).toBe(true);
    expect(
      env.doc.getElementById("service-management-body").innerHTML,
    ).toContain("worker.service");
    env.doc.getElementById("btn-back-services").click();
    expect(env.nav.services.classList.contains("hidden")).toBe(true);
    expect(env.nav.status.classList.contains("hidden")).toBe(false);
  });

  test("outages blink the child and both parents; recovery clears them", async () => {
    const env = setup();
    await flush();
    env.setPayload({
      status: "down",
      checked_at: 200,
      services: [service("api", "down")],
    });
    await env.SVC.poll();
    for (const id of ["btn-service-mgmt", "btn-system-status"]) {
      expect(
        env.doc.getElementById(id).classList.contains("tab-alert-red"),
      ).toBe(true);
    }
    expect(
      env.doc
        .getElementById("service-management-tabs")
        .querySelector('[data-service="api"]')
        .classList.contains("server-down"),
    ).toBe(true);
    env.setPayload({
      status: "up",
      checked_at: 215,
      services: [service("api")],
    });
    await env.SVC.poll();
    for (const id of ["btn-service-mgmt", "btn-system-status"]) {
      expect(
        env.doc.getElementById(id).classList.contains("tab-alert-red"),
      ).toBe(false);
      expect(env.doc.getElementById(id).classList.contains("server-up")).toBe(
        true,
      );
    }
  });

  test("unreachable checks replace green with unknown, then recover", async () => {
    const env = setup();
    await flush();
    env.fail(true);
    await env.SVC.poll();
    expect(
      env.doc
        .getElementById("btn-service-mgmt")
        .classList.contains("server-concern"),
    ).toBe(true);
    expect(
      env.doc.getElementById("service-management-body").innerHTML,
    ).toContain("connection refused");
    expect(
      env.doc.getElementById("service-management-body").innerHTML,
    ).toContain("Unknown");
    env.fail(false);
    await env.SVC.poll();
    expect(
      env.doc
        .getElementById("btn-service-mgmt")
        .classList.contains("server-up"),
    ).toBe(true);
    expect(
      env.doc.getElementById("service-management-body").innerHTML,
    ).not.toContain("connection refused");
  });

  test("monitors from boot while another page is open without overlapping requests", async () => {
    const env = setup();
    void env.SVC.poll();
    expect(env.calls()).toBe(1);
    await flush();
    expect(env.timers).toHaveLength(1);
    expect(env.timers[0].ms).toBe(15000);
    await env.timers[0].fn();
    expect(env.calls()).toBe(2);
  });

  test("renders downtime and recovery duration and escapes service metadata", () => {
    const html = renderServiceDetail(
      {
        ...service("api", "down"),
        label: "<img src=x>",
        down_since: 80,
        down_for_seconds: 120,
        events: [
          {
            at: 100,
            status: "up",
            detail: "<script>bad</script>",
            outage_seconds: 110,
          },
        ],
      },
      { checked_at: 200 },
    );
    expect(html).toContain("2m 0s");
    expect(html).toContain("Recovered after 1m 50s");
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("<script>");
  });
});
