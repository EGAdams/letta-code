import {
  buildTerminalQuery,
  TerminalLauncher,
} from "../abstract/terminal-launcher.interface.js";

let xtermLoad = null;

/** Lazy-load the locally vendored xterm bundle. */
export function loadXterm(doc = globalThis.document) {
  if (xtermLoad) return xtermLoad;
  const win = doc.defaultView || globalThis;
  const injectScript = (src) =>
    new Promise((resolve, reject) => {
      const script = doc.createElement("script");
      script.src = src;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`failed to load ${src}`));
      doc.head.appendChild(script);
    });
  xtermLoad = (async () => {
    if (!doc.querySelector("link[data-xterm-css]")) {
      const link = doc.createElement("link");
      link.rel = "stylesheet";
      link.href = "/vendor/xterm/xterm.css";
      link.setAttribute("data-xterm-css", "1");
      doc.head.appendChild(link);
    }
    if (!win.Terminal) await injectScript("/vendor/xterm/xterm.js");
    if (!win.FitAddon) await injectScript("/vendor/xterm/addon-fit.js");
    const Term = win.Terminal;
    const Fit = win.FitAddon && (win.FitAddon.FitAddon || win.FitAddon);
    if (!Term || !Fit) throw new Error("xterm failed to initialize");
    return { Term, Fit };
  })().catch((error) => {
    xtermLoad = null;
    throw error;
  });
  return xtermLoad;
}

/** Concrete TerminalLauncher backed by xterm.js and the dashboard WebSocket. */
export class XtermTerminalLauncher extends TerminalLauncher {
  /** @override */
  async open({
    hostEl,
    agentId = null,
    conversationId = null,
    onStatus = () => {},
    doc = globalThis.document,
  }) {
    const { Term, Fit } = await loadXterm(doc);
    const win = doc.defaultView || globalThis;
    const term = new Term({
      cursorBlink: false,
      disableStdin: true,
      fontSize: 18,
      fontFamily: '"Courier New", Courier, monospace',
      theme: { background: "#0b0e14", foreground: "#d3d7de" },
    });
    const fit = new Fit();
    term.loadAddon(fit);
    term.open(hostEl);
    term.write("\x1b[?7l");
    try {
      fit.fit();
    } catch {
      /* host may not be laid out yet */
    }

    let repaintTimer = null;
    const repaintTimers = [];
    const repaint = () => {
      try {
        term.resize(term.cols + 1, term.rows);
        term.resize(term.cols - 1, term.rows);
      } catch {
        /* best-effort paint nudge */
      }
    };
    const scheduleRepaint = () => {
      if (repaintTimer) win.clearTimeout(repaintTimer);
      repaintTimer = win.setTimeout(repaint, 200);
    };
    for (const delay of [700, 1800]) {
      repaintTimers.push(win.setTimeout(repaint, delay));
    }

    const proto = win.location.protocol === "https:" ? "wss" : "ws";
    const query = buildTerminalQuery({
      cols: term.cols,
      rows: term.rows,
      agentId,
      conversationId,
    });
    const ws = new win.WebSocket(
      `${proto}://${win.location.host}/api/terminal?${query}`,
    );
    ws.binaryType = "arraybuffer";

    const decoder = new TextDecoder();
    let closed = false;
    let pendingLines = [];
    const send = (frame) => {
      if (ws.readyState === win.WebSocket.OPEN) ws.send(JSON.stringify(frame));
    };
    ws.onopen = () => {
      onStatus("Connected to the scan conversation.");
      send({ t: "r", c: term.cols, r: term.rows });
      for (const text of pendingLines) send({ t: "i", d: `${text}\n` });
      pendingLines = [];
    };
    ws.onmessage = (event) => {
      term.write(
        typeof event.data === "string"
          ? event.data
          : decoder.decode(new Uint8Array(event.data)),
      );
      scheduleRepaint();
    };
    ws.onclose = () => {
      if (!closed) term.write("\r\n\x1b[38;5;244m[session ended]\x1b[0m\r\n");
      onStatus("Disconnected.");
    };
    ws.onerror = () => onStatus("Connection error.", true);

    const onResize = () => {
      try {
        fit.fit();
        send({ t: "r", c: term.cols, r: term.rows });
      } catch {
        /* ignore transient layout errors */
      }
    };
    win.addEventListener("resize", onResize);
    term.onResize(({ cols, rows }) => send({ t: "r", c: cols, r: rows }));

    return {
      dispose: () => {
        closed = true;
        if (repaintTimer) win.clearTimeout(repaintTimer);
        for (const timer of repaintTimers) win.clearTimeout(timer);
        win.removeEventListener("resize", onResize);
        try {
          ws.close();
        } catch {
          /* already closed */
        }
        try {
          term.dispose();
        } catch {
          /* already disposed */
        }
      },
      sendLine: (text) => {
        if (closed) return;
        if (ws.readyState === win.WebSocket.OPEN) {
          send({ t: "i", d: `${text}\n` });
        } else {
          pendingLines.push(text);
        }
      },
    };
  }
}

/** Compatibility function for focused callers that inject a simple factory. */
export function mountTerminal(request) {
  return new XtermTerminalLauncher().open(request);
}
