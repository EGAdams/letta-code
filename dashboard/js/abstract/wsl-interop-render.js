// wsl-interop-render.js — pure HTML for the WSLInterop Entry page.
//
// One card per machine, then the instructions. The instructions are always on
// the page, not only when something is red: the time somebody needs them is
// right after a reboot, and that is also when they are least likely to
// remember where the fix was written down.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

const STATE_TEXT = {
  enabled: "✓ Registered and enabled — Windows .exe files can run.",
  disabled:
    "✗ Registered but DISABLED — every Windows .exe fails with “Exec format error”.",
  missing: "✗ MISSING — every Windows .exe fails with “Exec format error”.",
  "not-wsl": "Not a WSL box — nothing to register.",
  unreachable: "⚠ Could not check this machine.",
};

const CARD_CLASS = { ok: "mtr-ok", warn: "mtr-warn", crit: "mtr-bad" };

function machineCard(m) {
  const service = m.binfmt_service
    ? `<p class="am-dim">systemd-binfmt: <code>${esc(m.binfmt_service)}</code></p>`
    : "";
  const detail = m.detail ? `<p class="am-dim">${esc(m.detail)}</p>` : "";
  const when = m.as_of
    ? `<p class="am-dim">Checked ${esc(new Date(m.as_of * 1000).toLocaleTimeString())}</p>`
    : "";
  return (
    `<div class="mtr-card ${CARD_CLASS[m.level] || "mtr-warn"}">` +
    `<h3>${esc(m.label)} <span class="am-dim">(${esc(m.host)})</span></h3>` +
    `<p>${esc(STATE_TEXT[m.state] || m.state)}</p>` +
    service +
    detail +
    when +
    "</div>"
  );
}

function instructions(d) {
  const cmd = d.register_command;
  return (
    '<div class="mtr-card mtr-info">' +
    "<h3>If a machine is red</h3>" +
    "<p>The <code>WSLInterop</code> entry in <code>/proc/sys/fs/binfmt_misc/</code> " +
    "is what lets WSL run Windows programs. When it is missing, anything that " +
    "launches a Windows <code>.exe</code> fails with <code>Exec format error</code>: " +
    "the browser-open ADW (rundll32.exe), the PC Monitor's PowerShell RAM reading, " +
    "the scanner and printer tools.</p>" +
    '<p class="mtr-fix-label">1. Open your own terminal on that machine. ' +
    "For another box, SSH in first (for example <code>ssh adamsl@100.72.34.38</code> " +
    "for Moms 46). It has to be a real terminal: <code>sudo</code> needs to ask for " +
    "your password, so it will not work from Claude Code’s <code>!</code> prompt " +
    "or from this dashboard.</p>" +
    '<p class="mtr-fix-label">2. Re-register the entry:</p>' +
    `<pre class="mtr-fix"><code>${esc(cmd)}</code></pre>` +
    '<p class="mtr-fix-label">3. Check it took:</p>' +
    '<pre class="mtr-fix"><code>cat /proc/sys/fs/binfmt_misc/WSLInterop   # first line: enabled\n' +
    "cmd.exe /c ver                            # prints the Windows version</code></pre>" +
    '<p class="am-dim">If <code>cmd.exe</code> answers <code>UtilAcceptVsock: accept4 ' +
    "failed 110</code> right after registering, run it again. That error went away " +
    "on its own the last time.</p>" +
    '<p class="mtr-fix-label">Or: restart WSL instead. In Windows PowerShell run ' +
    "<code>wsl --shutdown</code>, then open a new WSL terminal. This only helps " +
    "if <code>systemd-binfmt</code> registers the entry on that boot.</p>" +
    "<p>This page turns green on its next check, within 30 seconds.</p>" +
    "</div>"
  );
}

function permanentFixNote() {
  return (
    '<div class="mtr-card mtr-warn">' +
    "<h3>Note: this is not a permanent fix yet</h3>" +
    "<p>Re-registering only lasts until the next WSL restart. The entry is " +
    "supposed to be put back at every boot by <code>systemd-binfmt.service</code>, " +
    "from <code>/usr/lib/binfmt.d/WSLInterop.conf</code>. That service skips itself " +
    "(“start condition unmet”) when <code>/etc/wsl.conf</code> has " +
    "<code>systemd=true</code>. It broke the browser-open ADW on Rosemary46 on " +
    "Oct 28, and it shows <code>inactive</code> on all three machines here, so any " +
    "of them can lose the entry. Until the cause is fixed, expect the entry to vanish " +
    "after a reboot or <code>wsl --shutdown</code>.</p>" +
    "<p>Still to do, either of these: make <code>systemd-binfmt</code>’s start " +
    "condition succeed, or add a boot-time unit that re-registers the entry. " +
    "Once that is done, take this note off the page.</p>" +
    "</div>"
  );
}

export function renderWslInterop(d) {
  const machines = (d && d.machines) || [];
  return (
    machines.map(machineCard).join("") +
    instructions(d || {}) +
    permanentFixNote()
  );
}
