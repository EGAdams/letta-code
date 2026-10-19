import type { IManualChapter } from "../../../../the-factory/src/components/training-manual/interfaces";

export const workPanelChapter: IManualChapter = {
  id: "reading-the-work-panel",
  title: "Reading the work panel",
  summary:
    "Eight labelled rows, so waiting, stopped, failed and verified can never look alike.",
  blocks: [
    {
      kind: "text",
      text: "Toyota’s work panel sits under the conversation. It describes one piece of work at a time, using a separate labelled row for each question you would ask of it. Rows that have nothing to say are left out, so what you can see is what currently applies.",
    },
    {
      kind: "text",
      text: "“Right now” is the one-line summary of the condition. “Assignment” is the job in progress, such as Tax issues. “Record” is the expense being worked on, such as Expense #900001. “Requested operation” is what was asked for in words — opening supporting information, opening the editor, or setting a category to a named value.",
    },
    {
      kind: "text",
      text: "“Waiting for you” appears only when Toyota has asked a question and cannot continue until you answer it. “Problem” appears only for a failure or a cancellation. “Verified evidence” appears only when the stored value was read back out of the database. “Operation and run” names the operation ID and the ADW run the rest of the panel is describing.",
    },
    {
      kind: "note",
      title: "Only one row is proof",
      text: "Verified evidence is the only row that reports a value read back from the database after the save. Every other row describes an intention or a condition. A reply that sounds finished, a requested operation, and a run ID are not confirmations. If Verified evidence is absent, treat the save as unconfirmed and check it.",
    },
    {
      kind: "note",
      title: "Stopped is not undone",
      text: "Cancelling stops pending work. It does not undo a category that already saved — any earlier save is retained, and the Problem row says so rather than implying the record was put back. A failure is likewise honest that the stored value is not confirmed; it may have failed before or after the write, which is exactly why you re-read the record instead of guessing.",
    },
    {
      kind: "text",
      text: "Above the rows there is still a plain status line in the server’s own words, such as “verified: Verified training expense #900001”. It is deliberately unchanged and unpolished: it shows exactly what the server said, so you can compare the explained rows against the raw source and notice if they ever disagree.",
    },
    {
      kind: "text",
      text: "Everything in this lesson applies to practice expense #900001 in the separate training database. The panel marks its environment as training.",
    },
    {
      kind: "command",
      text: "interface WorkPresenter {\n    present( state: WorkState ): WorkFacts;\n}",
    },
    {
      kind: "text",
      text: "Presenter: TrainingWorkPresenter turns one saved checkpoint into WorkFacts — the set of separate statements above — and the panel renders those statements without deciding anything. The rule that only a verified checkpoint produces an evidence line lives in the presenter, where it is covered by tests, instead of being re-decided wherever text happens to be written.",
    },
    {
      kind: "text",
      text: "Because the panel depends on the WorkPresenter interface rather than on a particular presenter, a test can inject one that returns fixed WorkFacts, and a second assignment could later supply its own wording without touching the rendering. DashboardBrowserWorkspace receives the presenter at its composition root, in js/implementation/receptionist_work/src/composition.ts.",
    },
    {
      kind: "placeholder",
      title: "Panel history and side-by-side runs",
      text: "{to_be_implemented} — the panel shows the most recent six history lines and the latest run only. Comparing two runs in the panel, and filtering its history, are not built.",
    },
  ],
};
