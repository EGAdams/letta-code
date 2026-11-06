// all-monitors.js — composition root for the "All Monitors" tab. The only
// module that names concretes: FetchHttpClient, the catalog, the components.
import { MONITOR_CATALOG } from "../abstract/monitors/sources/monitor-catalog.js";
import { createMonitorSources } from "../abstract/monitors/sources/monitor-source-factory.js";
import { PollScheduler } from "../abstract/monitors/sources/poll-scheduler.js";
import { TabAlertObserver } from "../abstract/monitors/tab-alert-observer.js";
import { defineMonitorComponents } from "../components/define-monitor-components.js";
import { FetchHttpClient } from "../implementation/fetch-http-client.js";

const VISIBLE_MS = 15000;
const BACKGROUND_EVERY = 4; // while another tab is open, poll once a minute

export function bootAllMonitors(doc = document) {
  const view = doc.getElementById("all-monitors");
  const page = view?.querySelector("all-monitors-page");
  if (!page) return null;
  defineMonitorComponents();
  const sources = createMonitorSources(MONITOR_CATALOG, new FetchHttpClient());
  page.sources = sources;
  const tabObserver = new TabAlertObserver(
    doc.querySelector('[data-nav="main"][data-target="all-monitors"]'),
  );
  for (const s of sources) tabObserver.watch(s);
  let ticks = 0;
  const isActive = () =>
    !doc.hidden &&
    (view.classList.contains("active") || ticks++ % BACKGROUND_EVERY === 0);
  const scheduler = new PollScheduler(sources, {
    intervalMs: VISIBLE_MS,
    isActive,
  });
  new MutationObserver(() => {
    if (view.classList.contains("active")) scheduler.tick();
  }).observe(view, { attributes: true, attributeFilter: ["class"] });
  scheduler.start();
  return { sources, scheduler, tabObserver };
}

bootAllMonitors();
