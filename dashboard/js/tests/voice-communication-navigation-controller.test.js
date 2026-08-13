import { describe, expect, test } from "bun:test";
import { VoiceCommunicationNavigationController } from "../implementation/voice-communication-navigation-controller.js";
import { FakeDocument } from "./_fake-dom.js";

const specs = [
  { id: "overview", name: "Overview" },
  { id: "voice-session", name: "VoiceSession" },
];

function setup() {
  const doc = new FakeDocument();
  const plansNav = doc.createElement("nav");
  const voiceTab = doc.createElement("button");
  voiceTab.dataset.nav = "plans";
  voiceTab.dataset.target = "plans-voice-communication";
  plansNav.append(voiceTab);
  const voiceNav = doc.createElement("nav");
  voiceNav.classList.add("hidden");
  const back = doc.createElement("button");
  back.id = "btn-back-voice-communication";
  voiceNav.append(back);
  const frame = { contentWindow: { location: { hash: "" } } };
  const activated = [];
  const setActive = (nav, selector, tab) => {
    for (const item of nav.querySelectorAll(selector))
      item.classList.remove("active");
    tab.classList.add("active");
  };
  const controller = new VoiceCommunicationNavigationController({
    plansNav,
    voiceNav,
    frame,
    specs,
    activateView: (id) => activated.push(id),
    setActive,
    doc,
  });
  return { plansNav, voiceNav, voiceTab, back, frame, activated, controller };
}

describe("VoiceCommunicationNavigationController", () => {
  test("builds the dashboard's blue tabs from the interface specs", () => {
    const ctx = setup();
    expect(ctx.controller.bind()).toBe(true);
    const tabs = ctx.voiceNav.querySelectorAll(
      '[data-nav="voice-communication"][data-spec]',
    );
    expect(tabs.length).toBe(2);
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "Overview",
      "VoiceSession",
    ]);
  });

  test("opens the submenu on Overview and routes the content iframe", () => {
    const ctx = setup();
    ctx.controller.bind();
    ctx.controller.open();
    expect(ctx.plansNav.classList.contains("hidden")).toBe(true);
    expect(ctx.voiceNav.classList.contains("hidden")).toBe(false);
    expect(ctx.frame.contentWindow.location.hash).toBe("#overview");
    expect(
      ctx.voiceNav
        .querySelector('[data-spec="overview"]')
        .classList.contains("active"),
    ).toBe(true);
    expect(ctx.activated.at(-1)).toBe("plans-voice-communication");
  });

  test("selecting a blue tab changes the university page without adding another nav", () => {
    const ctx = setup();
    ctx.controller.bind();
    const session = ctx.voiceNav.querySelector('[data-spec="voice-session"]');
    session.click();
    expect(ctx.frame.contentWindow.location.hash).toBe("#voice-session");
    expect(session.classList.contains("active")).toBe(true);
  });

  test("Back restores Project Plans with Voice Communication selected", () => {
    const ctx = setup();
    ctx.controller.bind();
    ctx.controller.open();
    ctx.back.click();
    expect(ctx.voiceNav.classList.contains("hidden")).toBe(true);
    expect(ctx.plansNav.classList.contains("hidden")).toBe(false);
    expect(ctx.voiceTab.classList.contains("active")).toBe(true);
    expect(ctx.activated.at(-1)).toBe("plans-voice-communication");
  });
});
