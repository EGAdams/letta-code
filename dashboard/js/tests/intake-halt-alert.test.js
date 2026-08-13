import { describe, expect, test } from "bun:test";
import { IntakeHaltAlert } from "../implementation/intake-halt-alert.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(state) {
  const doc = new FakeDocument();
  const mk = (id) => {
    const el = doc.createElement("button");
    el.id = id;
    doc.add(el);
    return el;
  };
  const modal = mk("intake-halted-modal");
  modal.classList.add("hidden");
  const detail = mk("intake-halted-detail");
  const ack = mk("intake-halted-ack");

  const calls = [];
  const posts = [];
  const http = {
    getJSON: async (url) => {
      calls.push(url);
      if (state instanceof Error) throw state;
      return typeof state === "function" ? state() : state;
    },
    postJSON: async (url, body) => {
      posts.push([url, body]);
      return { ok: true, active: false };
    },
  };
  const alert = new IntakeHaltAlert({ http, doc, setInterval: () => 1 });
  return { alert, doc, modal, detail, ack, calls, posts };
}

const ACTIVE = {
  ok: true,
  active: true,
  event: {
    step: "source-counterpart-lookup",
    cause: "not enough arguments for format string",
    exception_type: "TypeError",
    document_path: "/scan.jpg",
  },
};

describe("IntakeHaltAlert", () => {
  test("raises the modal and shows the failing step while a halt is active", async () => {
    const { alert, modal, detail } = setup(ACTIVE);
    await alert.poll();
    expect(modal.classList.contains("hidden")).toBe(false);
    expect(detail.textContent).toContain("source-counterpart-lookup");
    expect(detail.textContent).toContain("TypeError");
    expect(detail.textContent).toContain("/scan.jpg");
  });

  test("keeps the modal hidden when no halt is active", async () => {
    const { alert, modal } = setup({ ok: true, active: false });
    await alert.poll();
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("Acknowledge clears server-side then hides the modal", async () => {
    const { alert, modal, posts } = setup(ACTIVE);
    await alert.poll();
    expect(modal.classList.contains("hidden")).toBe(false);
    await alert.acknowledge();
    expect(posts).toEqual([["/api/intake-halt-ack", {}]]);
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("a failed poll fetch does not throw", async () => {
    const { alert } = setup(new Error("network down"));
    await alert.poll();
  });

  test("hides locally even if the ack POST fails", async () => {
    const { alert, doc } = setup(ACTIVE);
    await alert.poll();
    alert._http.postJSON = async () => {
      throw new Error("backend down");
    };
    await alert.acknowledge();
    expect(
      doc.getElementById("intake-halted-modal").classList.contains("hidden"),
    ).toBe(true);
  });
});
