// Minimal DOM: the body's parts exist once the page HTML has been written.
function el() {
  const node = {
    writes: 0,
    _html: "",
    textContent: "",
    listeners: {},
    scrollHeight: 1000,
    scrollTop: 0,
    clientHeight: 200,
  };
  node.classList = {
    set: new Set(),
    add: (...c) => {
      for (const x of c) node.classList.set.add(x);
    },
    remove: (...c) => {
      for (const x of c) node.classList.set.delete(x);
    },
    contains: (c) => node.classList.set.has(c),
  };
  Object.defineProperty(node, "innerHTML", {
    configurable: true,
    get: () =>
      node.terminal
        ? node._html.replace(
            /(<pre[^>]*>)[\s\S]*?(<\/pre>)/,
            `$1${node.terminal.innerHTML}$2`,
          )
        : node._html,
    set: (v) => {
      node._html = v;
      node.writes += 1;
    },
  });
  Object.defineProperty(node, "textContent", {
    get: () => node._text || "",
    set: (value) => {
      node._text = value;
      node._html = value;
    },
  });
  node.addEventListener = (type, fn) => {
    node.listeners[type] = fn;
  };
  node.dispatchEvent = (event) => node.listeners[event.type]?.(event);
  return node;
}

export function fakeEnv(answers) {
  const body = el();
  const parts = {};
  Object.defineProperty(body, "innerHTML", {
    get: () => {
      let html = body._html;
      for (const part of Object.values(parts).sort(
        (a, b) => b.start - a.start,
      )) {
        html =
          html.slice(0, part.start) + part.innerHTML + html.slice(part.end);
      }
      return html;
    },
    set: (value) => {
      body._html = value;
      body.writes += 1;
    },
    configurable: true,
  });
  body.querySelector = (selector) => {
    const name = selector.match(/data-worker-part="(\w+)"/)?.[1];
    if (!name || !body._html.includes(`data-worker-part="${name}"`))
      return null;
    if (!parts[name]) {
      parts[name] = el();
      const marker = `data-worker-part="${name}">`;
      const start = body._html.indexOf(marker) + marker.length;
      const tail = body._html.slice(start);
      const isSpan = name === "updated";
      const next = isSpan
        ? tail.indexOf("</span>")
        : tail.search(
            /<div data-worker-part=|<p class="worker-activity-footer"/,
          );
      const end = isSpan
        ? start + next
        : start + (next >= 0 ? next : tail.length) - 6;
      parts[name].start = start;
      parts[name].end = end;
      parts[name]._html = body._html.slice(start, end);
    }
    parts[name].querySelector = (selector) => {
      if (
        selector === ".worker-activity-terminal" &&
        parts[name]._html.includes("worker-activity-terminal")
      ) {
        if (!parts[name].terminal) {
          parts[name].terminal = el();
          parts[name].terminal._html =
            parts[name]._html.match(/<pre[^>]*>([\s\S]*?)<\/pre>/)?.[1] || "";
        }
        return parts[name].terminal;
      }
      return null;
    };
    return parts[name];
  };
  const nodes = {
    "worker-activity-body": body,
    "btn-worker-activity": el(),
    "worker-legend": el(),
    "worker-activity": el(),
  };
  const doc = {
    visibilityState: "visible",
    getElementById: (id) => nodes[id] || null,
    addEventListener() {},
  };
  const timers = [];
  const win = {
    setTimeout: (fn, ms) => {
      timers.push({ fn, ms, live: true });
      return timers.length;
    },
    clearTimeout: (id) => {
      if (timers[id - 1]) timers[id - 1].live = false;
    },
  };
  let calls = 0;
  const pending = [];
  const http = {
    getJSON: () => {
      calls += 1;
      const answer = answers[Math.min(calls - 1, answers.length - 1)];
      return new Promise((resolve, reject) =>
        pending.push(() =>
          answer instanceof Error ? reject(answer) : resolve(answer),
        ),
      );
    },
  };
  const flush = async () => {
    while (pending.length) pending.shift()();
    await new Promise((r) => setTimeout(r, 0));
  };
  return { doc, win, http, nodes, parts, timers, flush, calls: () => calls };
}

export const ledger = (status) => ({
  ok: true,
  tasks_available: true,
  tasks: [{ id: "t1", agent: "codex", status }],
  worker: {
    status: "active",
    reason: "polling",
    service: { active: "active" },
  },
});
