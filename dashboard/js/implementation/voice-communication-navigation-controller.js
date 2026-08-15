/**
 * Owns the dashboard-level Voice Communication submenu.
 *
 * Interface names come from the same specs that render the document, so adding
 * a guide page cannot leave the blue dashboard tabs out of sync. The iframe is
 * content-only; selecting a dashboard tab changes its hash route.
 */
export class VoiceCommunicationNavigationController {
  constructor({
    plansNav,
    voiceNav,
    frame,
    specs,
    activateView,
    setActive,
    doc = globalThis.document,
  }) {
    this._plansNav = plansNav;
    this._voiceNav = voiceNav;
    this._frame = frame;
    this._specs = specs || [];
    this._activateView = activateView;
    this._setActive = setActive;
    this._doc = doc;
  }

  bind() {
    if (!this._plansNav || !this._voiceNav || !this._frame) return false;
    for (const oldTab of this._voiceNav.querySelectorAll(
      '[data-nav="voice-communication"][data-spec]',
    ))
      oldTab.remove();

    for (const spec of this._specs) {
      const tab = this._doc.createElement("button");
      tab.type = "button";
      tab.className = "tab";
      tab.dataset.nav = "voice-communication";
      tab.dataset.spec = spec.id;
      tab.textContent = spec.name;
      tab.addEventListener("click", () => this.show(spec.id, tab));
      this._voiceNav.append(tab);
    }

    this._voiceNav
      .querySelector("#btn-back-voice-communication")
      ?.addEventListener("click", () => this.back());
    return true;
  }

  open() {
    const first = this._specs[0];
    if (!first) return;
    this._plansNav.classList.add("hidden");
    this._voiceNav.classList.remove("hidden");
    const firstTab = this._voiceNav.querySelector(
      `[data-nav="voice-communication"][data-spec="${first.id}"]`,
    );
    this.show(first.id, firstTab);
  }

  show(specId, tab = null) {
    if (!this._specs.some((spec) => spec.id === specId)) return;
    if (tab)
      this._setActive?.(
        this._voiceNav,
        '[data-nav="voice-communication"][data-spec]',
        tab,
      );
    this._activateView?.("plans-voice-communication");
    const hash = `#${encodeURIComponent(specId)}`;
    try {
      if (this._frame.contentWindow.location.hash !== hash)
        this._frame.contentWindow.location.hash = hash;
    } catch {
      this._frame.src = `/voice_communication_plan.html${hash}`;
    }
  }

  back() {
    this._voiceNav.classList.add("hidden");
    this._plansNav.classList.remove("hidden");
    const voiceTab = this._plansNav.querySelector(
      '[data-nav="plans"][data-target="plans-voice-communication"]',
    );
    if (voiceTab)
      this._setActive?.(
        this._plansNav,
        '[data-nav="plans"][data-target]',
        voiceTab,
      );
    this._activateView?.("plans-voice-communication");
  }
}
