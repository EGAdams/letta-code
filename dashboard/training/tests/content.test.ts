import { describe, expect, test } from "bun:test";
import { trainingManual } from "../src/content";

describe("Published training curriculum", () => {
  test("chapter bookmarks and step identities are unique and stable", () => {
    const chapters = trainingManual.chapters.map((chapter) => chapter.id);
    expect(new Set(chapters).size).toBe(chapters.length);
    const steps = trainingManual.chapters
      .flatMap((chapter) => chapter.blocks)
      .filter((block) => block.kind === "step")
      .map((block) => block.id);
    expect(steps.length).toBeGreaterThanOrEqual(6);
    expect(new Set(steps).size).toBe(steps.length);
    for (const id of [...chapters, ...steps])
      expect(id).toMatch(/^[a-z][a-z0-9-]+$/);
  });
  test("teaches synthetic training, verification, ADWs and the exact console command", () => {
    const text = JSON.stringify(trainingManual);
    for (const term of [
      "900001",
      "$12.34",
      "Walgreens (RM)",
      "Walgreens (RJ)",
      "just tax-issues",
      "verified",
      "phase",
      "run",
      "synthetic",
      "Check interrupted operation",
    ]) {
      expect(text).toContain(term);
    }
    expect(text).not.toContain("just tax issues");
  });
  test("teaches how an assignment is installed, and admits only one is", () => {
    const patterns = trainingManual.chapters.find(
      (chapter) => chapter.id === "interfaces-and-patterns",
    )!;
    const text = patterns.blocks
      .map((block) => `${block.title ?? ""} ${block.text}`)
      .join("\n");
    // The registry is the one place an assignment is declared, and the capability list
    // Toyota speaks is derived from it -- a reader who only sees the prose must be able
    // to find both halves.
    expect(text).toContain("AssignmentPolicies");
    expect(text).toContain("AssignmentRegistry");
    expect(text).toMatch(/refus|not installed/i);
    // Registration being possible is not a second assignment working. Saying otherwise
    // would be exactly the overclaim the placeholders exist to prevent.
    const future = trainingManual.chapters.find(
      (chapter) => chapter.id === "coming-next",
    )!;
    const additional = future.blocks.find((block) =>
      /Additional assignments/.test(block.title ?? ""),
    )!;
    expect(additional.text).toContain("{to_be_implemented}");
    expect(JSON.stringify(trainingManual)).not.toMatch(
      /two assignments are installed|both assignments/i,
    );
  });
  test("every future capability is visibly marked", () => {
    const future = trainingManual.chapters.find(
      (chapter) => chapter.id === "coming-next",
    )!;
    expect(future.blocks.length).toBeGreaterThanOrEqual(4);
    for (const block of future.blocks) {
      expect(block.kind).toBe("placeholder");
      expect(block.text).toContain("{to_be_implemented}");
    }
  });
});
