/** Account-selection controls used by the Agent Assignments table. */
export function buildOauthAccountSelect({
  el,
  http,
  agentId,
  showStatus,
  getPendingModel = () => "",
  onSwitched = () => {},
}) {
  const select = el("select", { disabled: true });
  let current = "";
  const load = () => {
    const pending = getPendingModel();
    const url =
      `/api/agent-oauth-account?agent=${encodeURIComponent(agentId)}` +
      (pending ? `&model=${encodeURIComponent(pending)}` : "");
    return http
      .getJSON(url)
      .then((data) => {
        if (!data?.ok || !Array.isArray(data.options) || !data.options.length) {
          select.disabled = true;
          return;
        }
        select.innerHTML = "";
        for (const option of data.options) {
          select.appendChild(
            el("option", { value: option.provider, textContent: option.label }),
          );
        }
        const optionKeys = data.options.map((option) => option.provider);
        current =
          (current && optionKeys.includes(current) && current) ||
          data.current ||
          data.options[0].provider;
        select.value = current;
        select.disabled = false;
      })
      .catch(() => {
        select.disabled = true;
      });
  };

  select.addEventListener("change", async () => {
    const next = select.value;
    select.disabled = true;
    showStatus("Switching token…");
    try {
      const result = await http.postJSON("/api/agent-oauth-account", {
        agent: agentId,
        provider: next,
      });
      if (result?.ok) {
        current = result.provider || next;
        showStatus("Token switched.");
        onSwitched(result);
        select.dispatchEvent?.(
          new CustomEvent("agent-oauth-account:changed", {
            bubbles: true,
            detail: { agentId, account: result.account, provider: current },
          }),
        );
      } else {
        select.value = current;
        showStatus(result?.error || "Token change failed.", true);
      }
    } catch (error) {
      select.value = current;
      showStatus(`Token change failed: ${error.message}`, true);
    } finally {
      select.disabled = false;
    }
  });

  load();
  return { select, reload: load };
}

export function buildClaudeSdkAccountSelect({ el, http, showStatus }) {
  const select = el("select", { disabled: true });
  let current = "";
  const load = () =>
    http
      .getJSON("/api/claude-sdk-account")
      .then((data) => {
        if (!data?.ok || !Array.isArray(data.options) || !data.options.length) {
          select.disabled = true;
          return;
        }
        select.innerHTML = "";
        for (const option of data.options) {
          select.appendChild(
            el("option", { value: option.account, textContent: option.label }),
          );
        }
        const optionKeys = data.options.map((option) => option.account);
        current =
          (current && optionKeys.includes(current) && current) ||
          data.current ||
          data.options[0].account;
        select.value = current;
        select.disabled = false;
      })
      .catch(() => {
        select.disabled = true;
      });

  select.addEventListener("change", async () => {
    const next = select.value;
    select.disabled = true;
    showStatus(`Syncing Claude SDK token to ${next}…`);
    try {
      const result = await http.postJSON("/api/claude-sdk-account", {
        account: next,
      });
      if (!result?.ok) {
        select.value = current;
        showStatus(result?.error || "Claude SDK token change failed.", true);
        return;
      }
      current = result.current || next;
      showStatus(`Claude SDK token set to ${current}.`);
      select.dispatchEvent?.(
        new CustomEvent("claude-sdk-account:changed", {
          bubbles: true,
          detail: { agentId: "tool-run-claude-code-sdk" },
        }),
      );
      await load();
    } catch (error) {
      select.value = current;
      showStatus(`Claude SDK token change failed: ${error.message}`, true);
    } finally {
      select.disabled = false;
    }
  });

  load();
  return { select, reload: load };
}
