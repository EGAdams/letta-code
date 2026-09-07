"""Human-in-the-loop overlays that leave the affected dashboard tab visible."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from report_repair.models import Blocker

if TYPE_CHECKING:
    from playwright.sync_api import Page


def show_blocker(page: Page, blocker: Blocker) -> bool:
    """Show OK or YES/NO and return True for OK/YES, False for NO."""
    page.evaluate(
        """blocker => {
          document.getElementById('rol-report-repair-blocker')?.remove();
          window.__rolReportRepairChoice = null;
          const overlay = document.createElement('div');
          overlay.id = 'rol-report-repair-blocker';
          overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#0009;display:grid;place-items:center';
          const panel = document.createElement('div');
          panel.style.cssText = 'width:min(720px,92vw);max-height:82vh;overflow:auto;background:#c0c0c0;border:3px outset #fff;padding:22px;font:17px Arial;color:#111';
          const title = document.createElement('h2');
          title.textContent = `ROL Finance repair stopped — ${blocker.tab}`;
          const add = (label, value) => { const h=document.createElement('h3'); h.textContent=label;
            const p=document.createElement('p'); p.textContent=value; p.style.whiteSpace='pre-wrap'; panel.append(h,p); };
          panel.appendChild(title);
          add('Problem detected', blocker.problem);
          add('Missing information or action', blocker.missing);
          add('What you need to do', blocker.instruction);
          const buttons = document.createElement('div'); buttons.style.marginTop='20px';
          const answers = blocker.dialog === 'yes_no' ? ['YES','NO'] : ['OK'];
          for (const answer of answers) { const button=document.createElement('button');
            button.textContent=answer; button.style.cssText='margin-right:16px;padding:9px 30px;font-weight:bold';
            button.onclick=()=>{ window.__rolReportRepairChoice=answer; overlay.remove(); }; buttons.appendChild(button); }
          panel.appendChild(buttons); overlay.appendChild(panel); document.body.appendChild(overlay);
        }""",
        blocker.model_dump(),
    )
    while True:
        choice = cast(str | None, page.evaluate("window.__rolReportRepairChoice"))
        if choice:
            return choice in {"OK", "YES"}
        page.wait_for_timeout(250)

