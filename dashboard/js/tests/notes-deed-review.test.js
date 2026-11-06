import { describe, expect, test } from "bun:test";
import { markdownHtml } from "../boot/notes.js";

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
    expect(marks(html)).toBe(1);
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
});
