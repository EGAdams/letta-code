import { expect, test } from "bun:test";
import type {
  IManualBlock,
  IManualChapter,
} from "../../../../the-factory/src/components/training-manual/interfaces";
import { trainingManual } from "../src/content";

/** The labels DashboardBrowserWorkspace actually renders, in the order it renders them. */
const PANEL_ROWS = [
  "Right now",
  "Assignment",
  "Record",
  "Requested operation",
  "Waiting for you",
  "Problem",
  "Verified evidence",
  "Operation and run",
];

const chapter = (): IManualChapter => {
  const found = trainingManual.chapters.find(
    (candidate) => candidate.id === "reading-the-work-panel",
  );
  if (!found)
    throw new Error("the work panel lesson is not published in the manual");
  return found;
};
const prose = (): string =>
  chapter()
    .blocks.map((block: IManualBlock) => `${block.title ?? ""} ${block.text}`)
    .join("\n");
const order = (id: string): number =>
  trainingManual.chapters.findIndex((candidate) => candidate.id === id);

test("the lesson teaches every row the panel can show", () => {
  const text = prose();
  for (const row of PANEL_ROWS) expect(text).toContain(row);
});

test("the lesson is placed after watching a run and before the recovery explanation", () => {
  expect(order("reading-the-work-panel")).toBeGreaterThan(order("watch-a-run"));
  expect(order("reading-the-work-panel")).toBeLessThan(order("recovery"));
});

test("it says plainly that only the verified row means a confirmed save", () => {
  const text = prose().toLowerCase();
  expect(text).toContain("verified evidence");
  expect(text).toMatch(/read back|read from the database/);
  expect(text).toMatch(/does not undo|is retained|already saved/);
});

test("it distinguishes the server’s own status line from the explained rows", () => {
  expect(prose().toLowerCase()).toMatch(
    /status line|the server’s own words|exactly what the server/,
  );
});

test("it names the interface and the pattern a reader can go and read", () => {
  const text = prose();
  expect(text).toContain("WorkPresenter");
  expect(text).toContain("Presenter");
  expect(text).toContain("WorkFacts");
});

test("the lesson stays honest about the synthetic record and marks what is unbuilt", () => {
  const text = prose();
  expect(text).toContain("900001");
  expect(text).not.toContain("#557");
  const placeholders = chapter().blocks.filter(
    (block) => block.kind === "placeholder",
  );
  for (const block of placeholders)
    expect(block.text).toContain("{to_be_implemented}");
});
