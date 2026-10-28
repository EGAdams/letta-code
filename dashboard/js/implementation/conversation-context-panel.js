/**
 * buildConversationContextRow — the Input Options page's "Context" section:
 * a Win98-style progress bar for how full the agent's context window is,
 * plus the two-step conversation-management flow EG asked for:
 *
 *   Save to Memory  → POST /api/agent-compact  (Letta's built-in summarize:
 *                      writes a memory summary, shrinks history)
 *   Clear Conversation → PATCH /api/agent-reset-messages (wipes ALL messages;
 *                      irreversible, no partial "keep last N" exists in the
 *                      Letta API)
 *
 * Clear starts disabled and only re-enables after a Save succeeds, so a flush
 * can never run without something having just been pushed to memory first.
 * It re-disables after a successful Clear, so the next Clear needs its own
 * fresh Save.
 *
 * Clicking Clear also pops a small fixed-position tip next to the button,
 * styled like the yellow flagged-row tooltip in the ADW-generated report
 * pages (adw_interface_category_web_page.py's `.tip`/`.flagged` — a dark,
 * rounded, shadowed box, here tinted the same warning-yellow): it carries
 * whatever `showStatus` says about that click (clearing / cleared / error)
 * right at the place the operator is looking, and auto-hides after a few
 * seconds. Purely additive — the status line keeps being the system of
 * record, this is just an in-context echo of it.
 *
 *   el        → element factory, e.g. `this._el.bind(this)`
 *   http      → HttpClient
 *   agentId   → the Letta agent id this panel manages
 *   showStatus(msg, isError) → status-line callback
 *   confirm   → injectable window.confirm, for tests
 *
 * Returns { row, refresh } — the caller places `row` in the DOM and may call
 * `refresh()` after anything else changes the conversation (e.g. a Send).
 */
export function buildConversationContextRow({
  el,
  http,
  agentId,
  showStatus,
  confirm = (message) => globalThis.confirm(message),
}) {
  const row = el("div", { className: "conversation-context-panel" });
  row.style.cssText = "display:flex;flex-direction:column;gap:6px;";

  const label = el("div", { className: "cc-label" });
  label.style.cssText = "font-size:0.85rem;color:#555;";
  label.textContent = "Context: —";

  const shell = el("div", { className: "win98-progress-shell" });
  const fill = el("div", { className: "win98-progress-fill" });
  shell.appendChild(fill);

  const btnRow = el("div");
  btnRow.style.cssText = "display:flex;gap:8px;";
  const bs =
    "flex:1;padding:8px;font-size:0.85rem;border-radius:4px;border:0;cursor:pointer;color:#fff;";
  const saveBtn = el("button", { textContent: "Save to Memory" });
  saveBtn.style.cssText = `${bs}background:#6c757d;`;
  const clearBtn = el("button", {
    textContent: "Clear Conversation",
    disabled: true,
    title: "Save to Memory first.",
  });
  clearBtn.style.cssText = `${bs}background:#adb5bd;`;
  btnRow.append(saveBtn, clearBtn);

  const popup = el("div", { className: "cc-popup" });
  popup.style.cssText =
    "position:fixed;z-index:20;max-width:260px;padding:8px 11px;border-radius:6px;" +
    "background:#fff3a3;color:#1d2330;font-size:0.8rem;" +
    "box-shadow:0 4px 14px rgba(0,0,0,.25);pointer-events:none;display:none;";

  row.append(label, shell, btnRow, popup);

  let popupTimer = null;
  const showPopup = (text) => {
    popup.textContent = text;
    popup.style.display = "block";
    const rect = clearBtn.getBoundingClientRect?.() || { left: 0, bottom: 0 };
    popup.style.left = `${Math.max(8, rect.left)}px`;
    popup.style.top = `${rect.bottom + 8}px`;
    clearTimeout(popupTimer);
    popupTimer = setTimeout(() => {
      popup.style.display = "none";
    }, 3000);
  };

  const setClearEnabled = (enabled) => {
    clearBtn.disabled = !enabled;
    clearBtn.style.background = enabled ? "#c0392b" : "#adb5bd";
    clearBtn.title = enabled ? "" : "Save to Memory first.";
  };

  const refresh = () =>
    http
      .getJSON(`/api/agent-context?agent=${encodeURIComponent(agentId)}`)
      .then((d) => {
        if (!d?.ok) {
          label.textContent = "Context: unavailable";
          fill.style.width = "0%";
          return;
        }
        const { current, max } = d;
        const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0;
        label.textContent = `Context: ${current.toLocaleString()} / ${max.toLocaleString()} tokens (${Math.round(pct)}%)`;
        fill.style.width = `${pct}%`;
        fill.classList.toggle("warn", pct >= 70 && pct < 90);
        fill.classList.toggle("danger", pct >= 90);
      })
      .catch(() => {
        label.textContent = "Context: unavailable";
      });
  refresh();

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    showStatus("Saving important parts to memory…");
    try {
      const r = await http.postJSON("/api/agent-compact", { agent: agentId });
      if (!r?.ok) {
        showStatus(r?.error || "Could not save to memory.", true);
        return;
      }
      showStatus(
        `Saved to memory (${r.num_messages_before} → ${r.num_messages_after} messages).`,
      );
      setClearEnabled(true);
      refresh();
    } catch (e) {
      showStatus(`Could not save to memory: ${e.message}`, true);
    } finally {
      saveBtn.disabled = false;
    }
  });

  clearBtn.addEventListener("click", async () => {
    if (clearBtn.disabled) return;
    const ok = confirm(
      "This clears the conversation history and cannot be undone. Continue?",
    );
    if (!ok) return;
    clearBtn.disabled = true;
    showStatus("Clearing conversation…");
    showPopup("Clearing conversation…");
    try {
      const r = await http.postJSON("/api/agent-reset-messages", {
        agent: agentId,
      });
      if (!r?.ok) {
        const msg = r?.error || "Could not clear the conversation.";
        showStatus(msg, true);
        showPopup(msg);
        setClearEnabled(true);
        return;
      }
      showStatus("Conversation cleared.");
      showPopup("Conversation cleared.");
      setClearEnabled(false);
      refresh();
    } catch (e) {
      const msg = `Could not clear the conversation: ${e.message}`;
      showStatus(msg, true);
      showPopup(msg);
      setClearEnabled(true);
    }
  });

  return { row, refresh };
}
