import type { IManualChapter } from "../../../../the-factory/src/components/training-manual/interfaces";

export const recoveryPracticeChapter: IManualChapter = {
  id: "recovery-practice",
  title: "Your recovery practice session",
  summary:
    "Practise pausing, reloading, reconciling an interrupted save, cancelling, and retrying without saving twice.",
  blocks: [
    {
      kind: "note",
      title: "Do the first session before this one",
      text: "This session recovers a save, so it needs one that already happened. Finish “Your first practice session” first, so expense #900001 has a verified category to find your way back to. Everything here stays on the synthetic training record.",
    },
    {
      kind: "step",
      id: "pause-work",
      title: "1. Pause in the middle of the work",
      prompt: "Pause this work.",
      text: "Pausing keeps your place instead of discarding it. The work panel should still name expense #900001 and the assignment. Nothing is written to the record when you pause.",
    },
    {
      kind: "step",
      id: "resume-after-pause",
      title: "2. Ask where you left off",
      prompt: "Where did we leave off?",
      text: "Expect expense #900001 and its stored category. Toyota reads this from the retained checkpoint, so her answer should match what the editor last verified rather than what she last said.",
    },
    {
      kind: "step",
      id: "reload-and-resume",
      title: "3. Reload the dashboard and resume",
      prompt: "Which expense are we working on, and what is its category?",
      text: "Refresh the dashboard tab, then ask this. The checkpoint lives on the server, not in the page, so a reload should lose nothing. If the work panel comes back empty, say so in your notes — that is a real failure, not a slow refresh.",
    },
    {
      kind: "step",
      id: "reconcile-interrupted",
      title: "4. Reconcile an interrupted operation",
      prompt: "Change the category to Walgreens (RJ).",
      text: "Send the request, then refresh the dashboard while it is still working. When the panel returns it should offer “Check interrupted operation”. Use that button. It reads the stored record and tells you what actually happened; it never sends the save a second time. If the earlier save did land, this reports it as verified instead of writing a duplicate.",
    },
    {
      kind: "step",
      id: "cancel-pending",
      title: "5. Cancel pending work",
      prompt: "Stop what you are doing.",
      text: "Cancelling stops anything still waiting. It does not undo a category that already saved — any earlier save is retained, and Toyota should say so plainly rather than claiming she put the record back.",
    },
    {
      kind: "step",
      id: "safe-retry",
      title: "6. Retry safely",
      prompt: "What is the stored category for this expense right now?",
      text: "Read the stored value before asking for the change again. Request the save a second time only when the panel has not reported it as verified. Each request carries the version it expects to find, so a retry on an already-saved record reconciles with it instead of writing a duplicate.",
    },
    {
      kind: "step",
      id: "confirm-single-save",
      title: "7. Confirm you saved only once",
      prompt: "Show me its supporting information.",
      text: "Reopen the record and check that the category is the one you asked for and that the untouched fields — description, date, amount, mileage, notes — are unchanged. One requested change should leave exactly one change behind.",
    },
    {
      kind: "note",
      title: "Why there is no “crash it and see” step",
      text: "Recovery here is practised by reloading your own browser tab and by interrupting a request, never by stopping a shared service. Other people and agents use this machine, so breaking a service to make a demonstration would take their work down with it.",
    },
  ],
};
