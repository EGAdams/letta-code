import { describe, expect, test } from "bun:test";
import {
  isTyping,
  loadedCodeUrls,
  StaleCodeWatcher,
} from "../implementation/stale-code-watcher.js";

const headers = (map) => ({ get: (k) => map[k.toLowerCase()] ?? null });
function build({ files, typing = false, batch = 12, urls } = {}) {
  const reloads = [];
  const watcher = new StaleCodeWatcher({
    fetchFn: async (url) => {
      if (files[url] === "down") throw new Error("offline");
      if (files[url] === undefined) return { ok: false, headers: headers({}) };
      return {
        ok: true,
        headers: headers({
          "last-modified": files[url],
          "content-length": "1",
        }),
      };
    },
    listUrls: () => urls || Object.keys(files),
    canReload: () => !typing.now,
    reload: () => reloads.push(1),
    setInterval: () => 7,
    clearInterval: () => {},
    batchSize: batch,
  });
  return { watcher, reloads };
}

describe("StaleCodeWatcher", () => {
  test("requires fetchFn, listUrls and reload", () => {
    expect(() => new StaleCodeWatcher({})).toThrow();
  });

  test("does nothing while every file is unchanged", async () => {
    const files = { "/a.js": "t1", "/b.css": "t1" };
    const { watcher, reloads } = build({ files, typing: {} });
    await watcher.start();
    expect(await watcher.check()).toBe(false);
    expect(reloads.length).toBe(0);
  });

  test("reloads once a watched file changes", async () => {
    const files = { "/a.js": "t1", "/b.js": "t1" };
    const { watcher, reloads } = build({ files, typing: {} });
    await watcher.start();
    files["/b.js"] = "t2";
    expect(await watcher.check()).toBe(true);
    expect(reloads.length).toBe(1);
  });

  test("never reloads while someone is typing, then does once they stop", async () => {
    const files = { "/a.js": "t1" };
    const typing = { now: true };
    const { watcher, reloads } = build({ files, typing });
    await watcher.start();
    files["/a.js"] = "t2";
    expect(await watcher.check()).toBe(false);
    expect(await watcher.check()).toBe(false);
    expect(reloads.length).toBe(0);
    typing.now = false;
    expect(await watcher.check()).toBe(true);
    expect(reloads.length).toBe(1);
  });

  test("a failed or missing request is no news, never a reload or a throw", async () => {
    const files = { "/a.js": "t1", "/b.js": "t1" };
    const { watcher, reloads } = build({ files, typing: {} });
    await watcher.start();
    files["/a.js"] = "down";
    delete files["/b.js"];
    expect(await watcher.check()).toBe(false);
    expect(reloads.length).toBe(0);
  });

  test("checks a few files per round, round-robin, so a late file is still caught", async () => {
    const files = {};
    for (let i = 0; i < 30; i++) files[`/f${i}.js`] = "t1";
    const { watcher, reloads } = build({ files, typing: {}, batch: 10 });
    await watcher.start();
    files["/f29.js"] = "t2";
    expect(await watcher.check()).toBe(false);
    expect(await watcher.check()).toBe(false);
    expect(await watcher.check()).toBe(true);
    expect(reloads.length).toBe(1);
  });
});

describe("page helpers", () => {
  test("loadedCodeUrls keeps same-origin scripts and styles plus the page", () => {
    const perf = {
      getEntriesByType: () => [
        { name: "https://x.test/js/a.js?v=1" },
        { name: "https://x.test/css/b.css" },
        { name: "https://cdn.test/lib.js" },
        { name: "https://x.test/api/notes" },
      ],
    };
    expect(loadedCodeUrls(perf, "https://x.test").sort()).toEqual(
      [
        "https://x.test/",
        "https://x.test/css/b.css",
        "https://x.test/js/a.js?v=1",
      ].sort(),
    );
  });

  test("isTyping is true only for editable fields", () => {
    expect(isTyping({ activeElement: { tagName: "TEXTAREA" } })).toBe(true);
    expect(
      isTyping({ activeElement: { tagName: "DIV", isContentEditable: true } }),
    ).toBe(true);
    expect(isTyping({ activeElement: { tagName: "BUTTON" } })).toBe(false);
    expect(isTyping({})).toBe(false);
  });
});
