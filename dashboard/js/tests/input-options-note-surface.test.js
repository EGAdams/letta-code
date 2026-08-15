import { describe, expect, test } from "bun:test";
import { InputOptionsRenderer } from "../implementation/detail-renderers.js";
import { ReadOnlyNoteSurface } from "../implementation/textarea-note-surfaces.js";
import { FakeDocument } from "./_fake-dom.js";

function render({ surfaceFactory } = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.id = "box";
  doc.add(container);
  const posts = [];
  const api = new InputOptionsRenderer({
    http: {
      getJSON: async () => ({ ok: false, options: [] }),
      postJSON: async (url, body) => {
        posts.push({ url, body });
        return { ok: true, reply: "ack" };
      },
    },
    speech: { supported: false },
    agentName: "Toyota",
    agentId: "toyota-id",
    doc,
    storage: { getItem: () => null, setItem: () => {} },
    recorderFactory: () => ({ isRecording: false, start: async () => true }),
    ...(surfaceFactory ? { surfaceFactory } : {}),
  }).render("box", "toyota-id");
  return { container, api, posts };
}

describe("InputOptionsRenderer text surface", () => {
  test("defaults to the editable message box every agent page has", () => {
    const ctx = render();
    expect(ctx.api.note.editable).toBe(true);
    expect(ctx.api.textarea.readOnly).toBeFalsy();
  });

  test("sending from an editable box still clears it", async () => {
    const ctx = render();
    ctx.api.setText("hello there");
    await ctx.api.send();
    expect(ctx.api.note.getText()).toBe("");
    expect(ctx.posts.at(-1).body.text).toBe("hello there");
  });

  test("an injected read-only note surface is used as-is", () => {
    const ctx = render({ surfaceFactory: (o) => new ReadOnlyNoteSurface(o) });
    expect(ctx.api.textarea.readOnly).toBe(true);
    expect(ctx.api.note.editable).toBe(false);
  });

  test("sending never wipes a read-only note", async () => {
    const ctx = render({ surfaceFactory: (o) => new ReadOnlyNoteSurface(o) });
    ctx.api.setText("Today Roy and I worked on the scoreboard");
    await ctx.api.send();
    expect(ctx.api.note.getText()).toBe(
      "Today Roy and I worked on the scoreboard",
    );
    expect(ctx.posts.at(-1).body.text).toBe(
      "Today Roy and I worked on the scoreboard",
    );
  });
});
