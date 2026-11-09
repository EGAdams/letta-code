---
name: star-trek-bridge-highlight-review
description: Review yellow-highlighted text in a Dashboard Notes document through the Star Trek Bridge browser workflow. Use when a spoken command asks to open a named note (especially “Draft - Personal Representative’s Deed of Distribution”), find the first visible highlight, report its exact text and likely reason, then continue one highlight at a time. Use read-only inspection by default; never edit notes unless the user explicitly requests an edit.
---

# Star Trek Bridge highlight review

Use this skill for traceable, read-only review of highlights in Dashboard Notes. The browser bridge may expose `browser_open_dashboard_notes`, `browser_click`, `browser_read`, and an ADW screenshot/inspection path. `browser_read` alone is insufficient: it removes visual highlighting, and a click on `mark` is not a reliable way to identify which highlight was selected.

## Safety and capability boundary

- Do not edit, annotate, delete, save, or otherwise mutate the note or deed during review.
- Do not modify running production configuration, deploy, or claim that a browser action happened without a returned result.
- Use the available ADW/browser tool for every action and retain its returned task id (or explicitly say when the tool provides none). Report the task id with each important checkpoint.
- If the bridge lacks DOM inspection, computed styles, scrolling, or screenshots, say so and stop at the strongest verified result. Do not infer a highlight from plain text alone.
- A reason for a highlight is an interpretation. Label it as “likely reason” and distinguish it from text visibly present in the note.

## Workflow

1. **Parse the spoken request.** Confirm the target note title and whether the user asked only for review. If the request is ambiguous or asks to edit, ask before taking any mutating action.
2. **Open the existing note.** Call `browser_open_dashboard_notes` with the exact title, record the ADW task id, and verify from the result/screenshot that the requested note is open. Do not create a similarly named note.
3. **Inspect before clicking.** Use ADW screenshot/DOM inspection if available. Treat candidates in document order, not visual guesswork. Prefer this selector order:
   - an application-specific highlight selector exposed by the page (for example `[data-highlight]` or `[data-highlight-id]`),
   - `mark` elements whose computed `background-color` is yellow or a yellow highlight variant,
   - a documented notes-editor highlight class with a computed yellow background.

   Reject candidates that are hidden (`display:none`, `visibility:hidden`, zero-size, or detached) or outside the current document. Do not use a bare `mark` click when several candidates exist.
4. **Locate the first visible highlight robustly.** From the candidates in DOM order, choose the first one whose bounding rectangle has non-zero area and intersects the viewport. If none intersects, choose the first visible candidate in DOM order, call `scrollIntoView({block: "center", inline: "nearest"})`, then re-inspect and capture a screenshot. Do not call “first” based on `browser_read` text order alone.
5. **Identify exact text.** Read the selected element’s text from the DOM (`textContent` or the bridge’s equivalent), normalize only surrounding whitespace for display, and preserve internal punctuation, apostrophes, and line breaks when material. Record the selector/index and task id. If the DOM text and screenshot disagree, stop and report the discrepancy.
6. **Verify the selection.** After scrolling, take a screenshot or equivalent ADW visual check showing the selected yellow span in the viewport. A click is optional and should only be used when needed to focus/scroll; if used, click the specific element/coordinates returned by inspection and verify the post-click screenshot. Never use an ambiguous CSS `mark` click.
7. **Explain, then pause.** State the exact highlighted text, its location/ordinal (for example, “highlight 1 of N”), and a concise likely reason based on surrounding visible text. Ask whether to continue to the next highlight unless the spoken request already authorizes sequential review.
8. **Continue one at a time.** Re-run the DOM-order candidate query after each verified step because scrolling, selection, or lazy rendering may change the viewport. Advance by stable element identity/data id when available; otherwise use the previously verified text plus DOM position and re-check the screenshot. Never skip an unverified candidate.
9. **Finish with an audit trail.** Summarize highlights reviewed, exact text, interpretations, and ADW task ids. Explicitly say that no note/deed edits were made.

## Minimal inspection example

The following is a pattern for an ADW-capable browser evaluator, not a promise that these JavaScript calls are available through every bridge:

```js
const candidates = [...document.querySelectorAll(
  '[data-highlight], [data-highlight-id], mark, .highlight, .text-highlight'
)].filter((el) => {
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  const yellow = /yellow|rgb\(255,\s*255,\s*0\)|rgb\(255,\s*255,\s*153\)/i.test(
    `${style.backgroundColor} ${style.backgroundImage}`
  );
  return style.display !== 'none' && style.visibility !== 'hidden' &&
    rect.width > 0 && rect.height > 0 && yellow;
});
const inViewport = candidates.find((el) => {
  const r = el.getBoundingClientRect();
  return r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
});
const first = inViewport || candidates[0];
if (!inViewport && first) first.scrollIntoView({block: 'center', inline: 'nearest'});
// Re-inspect after scrolling; then return first.textContent and a screenshot.
```

If the page uses a different highlight representation, inspect the DOM and computed styles first and document the discovered selector in the audit trail. Do not broaden the selector to all colored text without visual verification.

## Spoken-command response shape

Use a compact, repeatable report:

> Opened **[note title]** — ADW task `[id]`.
> Highlight **[n]**: “**[exact text]**”
> Likely reason: [brief interpretation, clearly marked as an interpretation].
> Verified in viewport by [screenshot/inspection task id]. No edits made.

Then ask: “Continue to the next highlight?” unless the user already requested all highlights.
