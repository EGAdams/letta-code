import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { markdownHtml } from "../boot/notes.js";

const NOTES_CSS = readFileSync(
  new URL("../../css/dashboard.css", import.meta.url),
  "utf8",
);

const DEED =
  "2026-11-03_draft-personal-representative-s-deed-of-distribution.md";
const marks = (html) => (html.match(/<mark /g) || []).length;

describe("deed review marks follow what is still unresolved", () => {
  test("a finished Prepared by line is not marked; the open one is", () => {
    const source = [
      "# Personal Representative's Deed of Distribution",
      "- Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507",
      "- Drafted by: [NOT VERIFIED]",
      "- Prepared by: [NOT VERIFIED]",
    ].join("\n");
    const html = markdownHtml(source, { filename: DEED });
    expect(html).toContain(
      "Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507</li>",
    );
    expect(html).not.toMatch(/<mark[^>]*>[^<]*Louis Herbert Adams, Jr\./);
    expect(html).toMatch(
      /<mark class="notes-highlight-yellow notes-deed-review-preparer">Prepared by: \[NOT VERIFIED\]<\/mark>/,
    );
    expect(marks(html)).toBe(2); // the open Drafted by line is marked too
  });

  test("finished tax-parcel and legal-description lines lose the mark; bracketed ones keep it", () => {
    const html = markdownHtml(
      [
        "# Personal Representative's Deed of Distribution",
        "Tax Parcel No.: 41-14-31-404-015",
        "- Tax Parcel No.: 41-14-31-404-015 (from the 2017 deed; [VERIFY CURRENT PARCEL NO. WITH CITY ASSESSOR])",
        "Transfer tax exemption: [NOT VERIFIED]",
        "Transfer tax is paid.",
      ].join("\n"),
      { filename: DEED },
    );
    expect(marks(html)).toBe(2);
    expect(html).toContain("notes-deed-review-legal-description");
    expect(html).toContain("notes-deed-review-tax-language");
    expect(html).not.toMatch(
      /<mark[^>]*>Tax Parcel No\.: 41-14-31-404-015<\/mark>/,
    );
  });

  test("lines with no review keyword never get a mark, bracketed or not", () => {
    expect(
      marks(
        markdownHtml("COUNTY OF [___KENT_______]\nDated: [__________]", {
          filename: DEED,
        }),
      ),
    ).toBe(0);
  });

  test("any other open placeholder is marked, banner text and signing blanks are not", () => {
    const html = markdownHtml(
      [
        "# Personal Representative's Deed of Distribution",
        "conveys and distributes to [GRANTEE NAME(S) — NOT VERIFIED], whose address is [GRANTEE ADDRESS — NOT VERIFIED], Grantee,",
        "Items in [BRACKETS] are not verified and must be filled in.",
        "[VERIFY: the names match]",
      ].join("\n"),
      { filename: DEED },
    );
    expect(marks(html)).toBe(2);
    expect(html).toContain("notes-deed-review-open-item");
  });

  test("another note is never marked", () => {
    expect(
      marks(
        markdownHtml("Prepared by: [NOT VERIFIED]", { filename: "meeting.md" }),
      ),
    ).toBe(0);
  });

  test("the note text itself is untouched by rendering", () => {
    const source =
      "- Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507";
    markdownHtml(source, { filename: DEED });
    expect(source).toBe(
      "- Prepared by: Louis Herbert Adams, Jr., 511 Prince Street SE, Grand Rapids, MI 49507",
    );
  });

  test("a partly verified authority warning with links inside it is active too", () => {
    const warning =
      "[PARTIALLY VERIFIED: the closing statement was filed. Under [MCL 700.3954(2)](https://example.test/a) " +
      "the appointment ends a year later. VERIFY WITH THE PROBATE COURT OR A MICHIGAN ESTATE ATTORNEY: " +
      "confirm which recitals are required.]";
    const html = markdownHtml(
      [
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        warning,
        "## Other warnings",
        warning,
      ].join("\n"),
      { filename: DEED },
    );
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(1);
    expect(html).toMatch(/<span class="notes-deed-review-active-line">[^]*?VERIFY WITH THE PROBATE COURT[^]*?<\/span>/);
    expect(html).toContain("confirm which recitals are required.]</span>");
  });

  test("only the attorney/probate warning in the authority section is active", () => {
    const html = markdownHtml(
      [
        "# Personal Representative's Deed of Distribution",
        "## Authority of the Personal Representative",
        "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: confirm authority before recording.]",
        "## Other warnings",
        "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: this one stays still.]",
      ].join("\n"),
      { filename: DEED },
    );
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(1);
    expect(html).toContain(
      '<span class="notes-deed-review-active-line">[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: confirm authority before recording.]</span>',
    );
    expect(html).not.toContain(
      '<mark class="notes-highlight-yellow notes-deed-review-open-item notes-deed-review-active">',
    );
    expect(html).toContain(
      '<mark class="notes-highlight-yellow notes-deed-review-open-item">[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: this one stays still.]</mark>',
    );
  });

  test("only the active warning's background blinks; the text stays readable", () => {
    const activeRule = NOTES_CSS.match(
      /\.notes-preview \.notes-deed-review-active-line \{[\s\S]*?\n\}/,
    )?.[0];
    expect(activeRule).toContain(
      "animation: notes-active-deed-warning 1.4s steps(2, jump-none) infinite;",
    );
    expect(activeRule).toContain("background-color: transparent;");
    expect(activeRule).not.toContain("opacity");
    expect(activeRule).not.toContain("text-decoration: underline");
    expect(NOTES_CSS).toMatch(
      /@keyframes notes-active-deed-warning \{[\s\S]*?0%, 49% \{ background-color: #fff59d; \}[\s\S]*?50%, 100% \{ background-color: transparent; \}/,
    );
    const keyframes = NOTES_CSS.match(
      /@keyframes notes-active-deed-warning \{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/,
    )?.[0];
    expect(keyframes).toContain("background-color: #fff59d;");
    expect(keyframes).not.toContain("opacity");
    expect(NOTES_CSS).toContain("@media print");
    expect(NOTES_CSS).toMatch(
      /@media print \{[\s\S]*?\.notes-deed-review-active-line \{[\s\S]*?animation: none;[\s\S]*?opacity: 1;[\s\S]*?text-decoration: none;/,
    );
    const reducedMotion = NOTES_CSS.match(
      /@media \(prefers-reduced-motion: reduce\) \{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g,
    ) ?? [];
    for (const block of reducedMotion)
      expect(block).not.toContain(".notes-deed-review-active-line");
    expect(NOTES_CSS).toMatch(
      /\.notes-preview \.notes-deed-review-active-line \{[\s\S]*?animation: notes-active-deed-warning 1\.4s steps\(2, jump-none\) infinite;/,
    );
  });

  test("an explicit exact focus selects one paragraph and hides its marker", () => {
    const target = '[VERIFY: the 2017 deed names the grantee "Louis Adams"; confirm the source title.]';
    const html = markdownHtml([
      "# Personal Representative's Deed of Distribution",
      `<!-- notes-review-focus: ${target} -->`,
      "## Source of title",
      target,
      "## Authority of the Personal Representative",
      "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: this stays still.]",
    ].join("\n"), { filename: DEED });
    expect(html).toContain(
      '<span class="notes-deed-review-active-line">[VERIFY: the 2017 deed names the grantee &quot;Louis Adams&quot;; confirm the source title.]</span>',
    );
    expect(html).toContain("notes-deed-review-active-line");
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(1);
    expect(html).not.toContain("notes-review-focus");
    expect(html).toContain("notes-deed-review-open-item");
  });

  test("an explicit focus matches the saved yellow highlight's inner text", () => {
    const target = 'Confirm "Liber 4 of Plats, Page 31" before recording.';
    const savedDeedLine = `{{highlight:yellow}}${target}{{/highlight}}`;
    const html = markdownHtml([
      "# Personal Representative's Deed of Distribution",
      `<!-- notes-review-focus: ${target} -->`,
      savedDeedLine,
      "A completed legal description remains visible.",
      "[VERIFY: an unrelated open item]",
    ].join("\n"), { filename: DEED });
    expect(html).toContain(
      `<mark class="notes-highlight-yellow notes-deed-review-active-line">${target.replaceAll('"', "&quot;")}</mark>`,
    );
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(1);
    expect(html).toContain("A completed legal description remains visible.");
    expect(html).toContain("[VERIFY: an unrelated open item]");
    expect(html).not.toContain("opacity: 0");
  });

  test("an explicit missing focus suppresses the legacy authority pulse", () => {
    const html = markdownHtml([
      "# Personal Representative's Deed of Distribution",
      "<!-- notes-review-focus: [VERIFY: no longer in this note] -->",
      "## Authority of the Personal Representative",
      "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: do not blink this.]",
    ].join("\n"), { filename: DEED });
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(0);
  });

  test("a duplicated explicit focus suppresses every pulse", () => {
    const target = "[VERIFY: duplicated focus]";
    const html = markdownHtml([
      "# Personal Representative's Deed of Distribution",
      `<!-- notes-review-focus: ${target} -->`,
      "## Source of title",
      target,
      "## Authority of the Personal Representative",
      target,
    ].join("\n"), { filename: DEED });
    expect((html.match(/notes-deed-review-active-line/g) || []).length).toBe(0);
  });
});
