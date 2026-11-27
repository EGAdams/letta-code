// dom-live-activity.js — what agents and supervisors are doing right now.
// Reads /api/live-activity and shows it twice: agent steps are appended to the
// black #terminal-stream as they arrive, and supervisor records fill their own
// "Supervisor log" pane inside the Terminal tab, under the ADW Object Debugger.
// Display only: clearing or filtering never touches a record on any machine.
// One request per machine at a time; a machine that cannot be read says so.

const URL = "/api/live-activity";
const MACHINES = ["BATI", "SQMC", "R46", "DAD"];
const LOCAL_MS = 1000;
const REMOTE_MS = 5000;
const IDLE_MS = 15000;
const MAX_TERMINAL_LINES = 3000;
const MAX_RECORDS = 1500;
const CURRENT_KINDS = new Set(["status", "heartbeat", "timer", "blocker"]);
const BAD =
  /blocked|failed|stalled|stale|escalated|undelivered|failing|not fixed|unresolved/;

export function stamp(iso) {
  const date = new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return "—";
  const two = (n, w = 2) => String(n).padStart(w, "0");
  return `${two(date.getMonth() + 1)}-${two(date.getDate())} ${two(date.getHours())}:${two(date.getMinutes())}:${two(date.getSeconds())}.${two(date.getMilliseconds(), 3)}`;
}

export function identifiers(event) {
  return [
    event.task_id && `task ${event.task_id}`,
    event.bridge_task_id && `bridge ${event.bridge_task_id}`,
    event.request_id && `request ${event.request_id}`,
    event.adw_id && `adw ${event.adw_id}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function terminalLine(event) {
  const state = event.state ? ` [${event.state.toUpperCase()}]` : "";
  return `${stamp(event.at)} ${event.machine}/${event.agent}${state} ${event.message}`;
}

export function matches(event, { machine = "", agent = "", text = "" }) {
  if (machine && event.machine !== machine) return false;
  if (agent && event.agent !== agent) return false;
  const needle = text.trim().toLowerCase();
  if (!needle) return true;
  return `${event.message} ${identifiers(event)}`
    .toLowerCase()
    .includes(needle);
}

export function createLiveActivity({ doc = document, win = window, http }) {
  const view = doc.getElementById("terminal");
  const stream = doc.getElementById("terminal-stream");
  if (!view || !stream || doc.getElementById("supervisor-log")) return null;

  const filters = { machine: "", agent: "", text: "" };
  const records = new Map(); // key -> supervisor record
  const gaps = new Map(); // machine -> [text]
  const announced = new Set();
  const terminalNodes = [];
  const cursors = new Map();
  const timers = new Map();
  let hidden = new Set();
  let stopped = false;

  const make = (tag, className, text) => {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const pane = make("details", "supervisor-log");
  pane.id = "supervisor-log";
  pane.open = true;
  pane.appendChild(make("summary", "", "Supervisor log"));
  // Not "terminal-toolbar": the ADW debugger mounts before the first element of that class.
  const bar = make("div", "supervisor-bar");
  const select = (name, label, values) => {
    const box = make("select");
    box.setAttribute("aria-label", label);
    box.id = `supervisor-${name}`;
    for (const value of ["", ...values]) {
      const option = make("option", "", value || `All ${label}s`);
      option.value = value;
      box.appendChild(option);
    }
    box.addEventListener("change", () => {
      filters[name] = box.value;
      draw();
    });
    bar.appendChild(box);
    return box;
  };
  select("machine", "machine", MACHINES);
  const agentBox = select("agent", "agent", []);
  const search = make("input");
  search.type = "search";
  search.id = "supervisor-search";
  search.placeholder = "request, task, ADW or mail id";
  search.addEventListener("input", () => {
    filters.text = search.value;
    draw();
  });
  bar.appendChild(search);
  const clear = make("button", "am-btn", "Clear view");
  clear.type = "button";
  clear.addEventListener("click", () => {
    hidden = new Set(records.keys());
    draw();
  });
  bar.appendChild(clear);
  pane.appendChild(bar);
  const now = make("div", "supervisor-now");
  const timeline = make("div", "supervisor-timeline");
  timeline.setAttribute("role", "log");
  pane.appendChild(now);
  pane.appendChild(timeline);
  view.appendChild(pane);

  function lineNode(text, state) {
    return make(
      "div",
      BAD.test(state || "")
        ? "terminal-line terminal-line-bad"
        : "terminal-line",
      text,
    );
  }

  function toTerminal(events) {
    if (!events.length) return;
    const follow =
      stream.scrollHeight - stream.scrollTop - stream.clientHeight <= 24;
    const add = (node) => {
      stream.appendChild(node);
      terminalNodes.push(node);
    };
    for (const event of events) {
      const key = `${event.machine}|${event.task_id}`;
      if (event.kind === "task.stalled") {
        const once = `${key}|stalled|${event.at}`;
        if (announced.has(once)) continue;
        announced.add(once);
      } else if (!announced.has(key)) {
        announced.add(key);
        add(
          make(
            "div",
            "terminal-line terminal-line-head",
            `── agent ${event.agent} on ${event.machine} · ${identifiers(event)} ──`,
          ),
        );
      }
      add(lineNode(terminalLine(event), event.state));
    }
    while (terminalNodes.length > MAX_TERMINAL_LINES)
      terminalNodes.shift().remove();
    if (follow) stream.scrollTop = stream.scrollHeight;
  }

  function keep(payload) {
    const machine = payload.machine;
    gaps.set(machine, payload.gaps || []);
    if (!payload.ok) return;
    for (const [key, record] of records)
      if (record.machine === machine && CURRENT_KINDS.has(record.kind))
        records.delete(key);
    for (const event of payload.supervisor_events || []) {
      const key = CURRENT_KINDS.has(event.kind)
        ? `${machine}|${event.kind}|${event.message}`
        : `${machine}|${event.at}|${event.kind}|${event.state}|${event.task_id}|${event.message}`;
      records.set(key, event);
    }
    // Failed and blocked agent tasks are kept here too, so they stay findable.
    for (const event of payload.agent_events || [])
      if (BAD.test(event.state || ""))
        records.set(
          `${machine}|${event.at}|${event.kind}|${event.task_id}`,
          event,
        );
    if (records.size > MAX_RECORDS) {
      const old = [...records].sort((a, b) => a[1].at.localeCompare(b[1].at));
      for (const [key] of old.slice(0, records.size - MAX_RECORDS))
        records.delete(key);
    }
  }

  function draw() {
    const known = new Set([...agentBox.children].map((o) => o.value));
    for (const record of records.values())
      if (!known.has(record.agent)) {
        known.add(record.agent);
        const option = make("option", "", record.agent);
        option.value = record.agent;
        agentBox.appendChild(option);
      }
    const follow =
      timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight <= 24;
    now.textContent = "";
    timeline.textContent = "";
    const shown = [...records]
      .filter(
        ([key, r]) =>
          matches(r, filters) &&
          (CURRENT_KINDS.has(r.kind) || !hidden.has(key)),
      )
      .map(([, r]) => r)
      .sort((a, b) => a.at.localeCompare(b.at));
    for (const r of shown) {
      const ids = identifiers(r);
      const text = `${CURRENT_KINDS.has(r.kind) ? "now" : stamp(r.at)} ${r.machine}/${r.agent} ${r.kind}${r.state ? ` [${r.state}]` : ""} ${r.message}${ids ? `  {${ids}}` : ""}  <${r.source}>`;
      (CURRENT_KINDS.has(r.kind) ? now : timeline).appendChild(
        lineNode(text, r.state),
      );
    }
    for (const [machine, list] of gaps)
      if (!filters.machine || filters.machine === machine)
        for (const gap of list)
          now.appendChild(
            make("div", "terminal-line terminal-line-gap", `[gap] ${gap}`),
          );
    if (!shown.length)
      timeline.appendChild(
        make("div", "terminal-empty", "No supervisor records match."),
      );
    if (follow) timeline.scrollTop = timeline.scrollHeight;
  }

  let localName = "";

  async function poll(machine) {
    if (stopped) return;
    const after = cursors.get(machine);
    const query = [
      machine && `machine=${machine}`,
      after !== undefined && `after=${after}`,
    ]
      .filter(Boolean)
      .join("&");
    let payload;
    try {
      payload = await http.getJSON(query ? `${URL}?${query}` : URL);
    } catch (error) {
      payload = {
        ok: false,
        machine: machine || localName || "this machine",
        gaps: [
          `${machine || "this machine"}: ${error.message || "request failed"}`,
        ],
      };
    }
    if (!machine && payload.ok) localName = payload.machine;
    if (payload.ok) cursors.set(machine, payload.cursor);
    toTerminal(payload.agent_events || []);
    keep(payload);
    draw();
  }

  function loop(machine) {
    if (stopped || (machine && machine === localName)) return;
    void poll(machine).finally(() => {
      const active =
        view.classList.contains("active") && doc.visibilityState !== "hidden";
      const wait = active ? (machine ? REMOTE_MS : LOCAL_MS) : IDLE_MS;
      timers.set(
        machine,
        win.setTimeout(() => loop(machine), wait),
      );
    });
  }

  // This machine first, so it is not also asked for over SSH under its own name.
  const started = poll("").then(() => {
    timers.set(
      "",
      win.setTimeout(() => loop(""), LOCAL_MS),
    );
    for (const machine of MACHINES) loop(machine);
  });

  return {
    poll,
    started,
    stop() {
      stopped = true;
      for (const timer of timers.values()) win.clearTimeout(timer);
      pane.remove();
    },
  };
}
