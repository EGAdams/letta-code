import { describe, expect, test } from "bun:test";
import {
  OpenRequestsChip,
  summarizeRequests,
} from "../implementation/open-requests-chip.js";

const payload = (open) => ({ requests: { available: true, open } });
const request = (timer, phase = "idle") => ({
  title: "job",
  timer,
  phase,
  since_progress: "12 min",
  next_action: "do it",
});

function fakeDoc() {
  const element = () => ({
    style: {},
    children: [],
    textContent: "",
    appendChild(child) {
      child.parent = this;
      this.children.push(child);
    },
    remove() {
      this.parent.children = this.parent.children.filter((c) => c !== this);
    },
    setAttribute() {},
    addEventListener() {},
  });
  return { body: element(), createElement: element };
}

describe("open requests marker", () => {
  test("counts stalled and blocked requests, acknowledged or not", () => {
    const out = summarizeRequests(
      payload([
        request("escalated"),
        request("warning", "blocked"),
        request("ok"),
      ]),
    );
    expect(out.label).toBe(
      "⚠ 2 Bridge requests need attention · 1 idle · 1 blocked",
    );
    expect(out.items[0].next).toBe("do it");
  });

  test("an unreadable gateway is unknown, never clear", () => {
    expect(summarizeRequests({}).label).toContain("unknown");
  });

  test("stays until nothing needs attention, then goes", async () => {
    const doc = fakeDoc();
    let open = [request("escalated")];
    const chip = new OpenRequestsChip({
      doc,
      http: { getJSON: async () => payload(open) },
      setInterval: null,
    });
    await chip.poll();
    await chip.poll();
    expect(doc.body.children.length).toBe(1);
    open = [request("ok")];
    await chip.poll();
    expect(doc.body.children.length).toBe(0);
  });
});
