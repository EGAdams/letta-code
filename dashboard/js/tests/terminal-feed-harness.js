// Minimal fake DOM for createTerminalFeed — no real browser, no network.
function fakeElement() {
  const node = {
    textContent: "",
    className: "",
    scrollHeight: 1000,
    scrollTop: 0,
    clientHeight: 200,
    children: [],
    listeners: {},
  };
  node.appendChild = (child) => {
    child._parent = node;
    node.children.push(child);
  };
  node.remove = () => {
    const parent = node._parent;
    if (!parent) return;
    const i = parent.children.indexOf(node);
    if (i >= 0) parent.children.splice(i, 1);
  };
  node.addEventListener = (type, fn) => {
    node.listeners[type] = fn;
  };
  // Clearing textContent directly (as `clear()` does) must also drop children,
  // matching real DOM semantics where `el.textContent = ""` removes all nodes.
  let text = "";
  Object.defineProperty(node, "textContent", {
    get: () => text,
    set: (value) => {
      text = value;
      if (value === "") node.children.length = 0;
    },
  });
  return node;
}

export function fakeTerminalEnv(answers) {
  const stream = fakeElement();
  const status = fakeElement();
  const clearButton = fakeElement();
  const view = fakeElement();
  view.classList = {
    active: false,
    contains: (name) => (name === "active" ? view.classList.active : false),
  };
  const nodes = {
    terminal: view,
    "terminal-stream": stream,
    "terminal-status": status,
    "terminal-clear": clearButton,
  };
  let visibilityState = "visible";
  const docListeners = {};
  const doc = {
    get visibilityState() {
      return visibilityState;
    },
    getElementById: (id) => nodes[id] || null,
    createElement: () => fakeElement(),
    addEventListener: (type, fn) => {
      docListeners[type] = fn;
    },
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
  const posts = [];
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
    postJSON: async (url, body) => {
      posts.push({ url, body });
      return { ok: true, terminal_clear_epoch: 1 };
    },
  };
  const flush = async () => {
    while (pending.length) pending.shift()();
    await new Promise((r) => setTimeout(r, 0));
  };
  return {
    doc,
    win,
    http,
    nodes,
    stream,
    status,
    clearButton,
    timers,
    flush,
    calls: () => calls,
    posts,
    setVisibility: (value) => {
      visibilityState = value;
      docListeners.visibilitychange?.();
    },
  };
}
