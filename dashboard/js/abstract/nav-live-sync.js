// nav-live-sync.js — pure diff between the sidebar's current top-level tabs
// and the tabs parsed out of a freshly fetched dashboard.html.
//
// DOM-free on purpose: implementation/dom-nav-live-sync.js owns reading the
// live DOM and applying the result, so this is the one piece of "what
// changed" logic that stays unit-testable without a browser.

/**
 * @param {string[]} currentTargets - `data-target`s already rendered.
 * @param {{target: string, label: string}[]} nextTabs - tabs found in the
 *   markup just fetched, in document order.
 * @returns {{toAdd: {target: string, label: string}[], toRemove: string[]}}
 */
export function diffNavTabs(currentTargets, nextTabs) {
  const currentSet = new Set(currentTargets);
  const nextSet = new Set(nextTabs.map((tab) => tab.target));
  return {
    toAdd: nextTabs.filter((tab) => !currentSet.has(tab.target)),
    toRemove: currentTargets.filter((target) => !nextSet.has(target)),
  };
}
