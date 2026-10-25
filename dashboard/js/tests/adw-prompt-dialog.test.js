import { describe, expect, test } from "bun:test";
import { AdwPromptDialog } from "../implementation/adw-prompt-dialog.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(state) {
  const doc = new FakeDocument();
  const mk = (id) => {
    const el = doc.createElement("div");
    el.id = id;
    doc.add(el);
    return el;
  };
  const modal = mk("adw-prompt-modal");
  modal.classList.add("hidden");
  const title = mk("adw-prompt-title");
  const question = mk("adw-prompt-question");
  const detail = mk("adw-prompt-detail");
  const yes = mk("adw-prompt-yes");
  const no = mk("adw-prompt-no");

  const posts = [];
  const http = {
    getJSON: async () => {
      if (state.value instanceof Error) throw state.value;
      return state.value;
    },
    postJSON: async (url, body) => {
      posts.push([url, body]);
      if (state.postError) throw state.postError;
      return { ok: true };
    },
  };
  const dialog = new AdwPromptDialog({ http, doc, setInterval: () => 1 });
  return { dialog, modal, title, question, detail, yes, no, posts };
}

const OPEN = {
  ok: true,
  active: true,
  prompt: {
    id: "abc123",
    question: "Run WSL Compact?",
    detail: "Windows 10 is still warn: C: 3.2 GB free",
    source: "adw_interface_pc_doctor",
    status: "pending",
  },
};
const NONE = { ok: true, active: false, prompt: null };

describe("AdwPromptDialog", () => {
  test("raises the modal with the question while one is open", async () => {
    const { dialog, modal, title, question, detail } = setup({ value: OPEN });
    await dialog.poll();
    expect(modal.classList.contains("hidden")).toBe(false);
    expect(title.textContent).toBe("PC Doctor");
    expect(question.textContent).toBe("Run WSL Compact?");
    expect(detail.textContent).toContain("3.2 GB free");
  });

  test("stays hidden when nothing is being asked", async () => {
    const { dialog, modal } = setup({ value: NONE });
    await dialog.poll();
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("Yes posts the answer for that question and hides the modal", async () => {
    const { dialog, modal, yes, posts } = setup({ value: OPEN });
    dialog.start();
    await dialog.poll();
    yes.click();
    await Promise.resolve();
    await Promise.resolve();
    expect(posts).toEqual([
      ["/api/adw-prompt-answer", { id: "abc123", answer: "yes" }],
    ]);
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("No posts no", async () => {
    const { dialog, posts } = setup({ value: OPEN });
    await dialog.poll();
    await dialog.answer("no");
    expect(posts).toEqual([
      ["/api/adw-prompt-answer", { id: "abc123", answer: "no" }],
    ]);
  });

  test("a withdrawn or expired question hides itself on the next poll", async () => {
    const state = { value: OPEN };
    const { dialog, modal } = setup(state);
    await dialog.poll();
    state.value = NONE;
    await dialog.poll();
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("answering with nothing open posts nothing", async () => {
    const { dialog, posts } = setup({ value: NONE });
    await dialog.poll();
    await dialog.answer("yes");
    expect(posts).toEqual([]);
  });

  test("a failed answer POST still hides; the next poll re-raises it", async () => {
    const state = { value: OPEN, postError: new Error("backend down") };
    const { dialog, modal } = setup(state);
    await dialog.poll();
    await dialog.answer("yes");
    expect(modal.classList.contains("hidden")).toBe(true);
    await dialog.poll();
    expect(modal.classList.contains("hidden")).toBe(false);
  });

  test("a failed poll does not throw or change the modal", async () => {
    const { dialog, modal } = setup({ value: new Error("network down") });
    await dialog.poll();
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("titles come from the asking ADW's name", () => {
    expect(AdwPromptDialog.titleFor("adw_interface_pc_doctor")).toBe(
      "PC Doctor",
    );
    expect(AdwPromptDialog.titleFor("adw_interface_wsl_compact.py")).toBe(
      "Wsl Compact",
    );
    expect(AdwPromptDialog.titleFor("")).toBe("ADW");
  });
});
