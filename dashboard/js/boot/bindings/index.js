// bindings/index.js — attach every sidebar listener, once, at boot.
//
// The whole set is gated on the eleven nav elements the ladders assume exist:
// a page missing one of them is a broken build, and half-binding it would be
// worse than binding nothing.

import { bindAgentNav } from "./agent-nav.js";
import { bindFinanceNav } from "./finance-nav.js";
import { bindInfraNav } from "./infra-nav.js";
import { bindMainNav } from "./main-nav.js";
import { bindPlansNav } from "./plans-nav.js";

export function bindNavigation(deps) {
  const { nav } = deps;
  const required = [
    nav.main,
    nav.status,
    nav.agents,
    nav.agentDetail,
    nav.servers,
    nav.ssh,
    nav.plans,
    nav.agentBlocks,
    nav.processFlows,
    nav.voiceCommunication,
    nav.rolFinance,
    nav.rolFinanceReports,
  ];
  if (!required.every(Boolean)) return false;

  bindMainNav(deps);
  bindPlansNav(deps);
  bindFinanceNav(deps);
  bindAgentNav(deps);
  bindInfraNav(deps);
  return true;
}
