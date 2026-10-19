import { describe, expect, test } from "bun:test";
import type {
  IManualBlock,
  IManualChapter,
} from "../../../../the-factory/src/components/training-manual/interfaces";
import { trainingManual } from "../src/content";

const chapter = (): IManualChapter => {
  const found = trainingManual.chapters.find(
    (candidate) => candidate.id === "recovery-practice",
  );
  if (!found)
    throw new Error(
      "the recovery practice session is not published in the manual",
    );
  return found;
};

const steps = (): readonly IManualBlock[] =>
  chapter().blocks.filter((block) => block.kind === "step");

const words = (blocks: readonly IManualBlock[]): string =>
  JSON.stringify(blocks).toLowerCase();

describe("Recovery practice session", () => {
  test("is published as a working session, not another block of prose", () => {
    const practice = steps();
    expect(practice.length).toBeGreaterThanOrEqual(6);
    for (const step of practice) {
      expect(step.id).toMatch(/^[a-z][a-z0-9-]+$/);
      expect(step.title!.length).toBeGreaterThan(0);
      // A step the reader cannot actually perform is prose with a checkbox on it.
      expect(step.prompt!.trim().length).toBeGreaterThan(0);
      expect(step.text.trim().length).toBeGreaterThan(0);
    }
    const ids = practice.map((step) => step.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("follows the first practice session so the reader already has a saved value to recover", () => {
    const order = trainingManual.chapters.map((candidate) => candidate.id);
    expect(order.indexOf("recovery-practice")).toBeGreaterThan(
      order.indexOf("first-session"),
    );
  });

  test("practises every recovery behaviour the reader has to trust", () => {
    const ids = steps().map((step) => step.id);
    for (const behaviour of [
      "pause-work",
      "resume-after-pause",
      "reload-and-resume",
      "reconcile-interrupted",
      "cancel-pending",
      "safe-retry",
    ]) {
      expect(ids).toContain(behaviour);
    }
  });

  test("teaches reconciliation as checking the stored value, never as saving again", () => {
    const reconcile = steps().find(
      (step) => step.id === "reconcile-interrupted",
    )!;
    const text = words([reconcile]);
    expect(text).toContain("check interrupted operation");
    // The whole point of the expected-version lock: a retry must not write a second time.
    expect(words(steps())).toContain("duplicate");
  });

  test("retrying is gated on reading the stored value first", () => {
    const retry = steps().find((step) => step.id === "safe-retry")!;
    expect(words([retry])).toContain("verified");
  });

  test("is honest that cancelling does not undo a category that already saved", () => {
    const cancel = steps().find((step) => step.id === "cancel-pending")!;
    const text = words([cancel]);
    expect(text).toMatch(/does not undo|already saved|is retained/);
  });

  test("never asks the reader to break a shared service to practise recovery", () => {
    const text = words(chapter().blocks);
    for (const destructive of [
      "kill ",
      "pkill",
      "restart the dashboard",
      "stop the server",
    ]) {
      expect(text).not.toContain(destructive);
    }
  });

  test("keeps the practice on the synthetic record", () => {
    const text = words(chapter().blocks);
    expect(text).toContain("900001");
    expect(text).not.toContain("#557");
  });
});
