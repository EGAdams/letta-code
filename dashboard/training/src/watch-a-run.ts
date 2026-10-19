import type { IManualChapter } from "../../../../the-factory/src/components/training-manual/interfaces";

export const watchARunChapter: IManualChapter = {
  id: "watch-a-run",
  title: "Your second practice session",
  summary:
    "Watch Toyota’s checkpoint and compare the recorded phases before and after a request.",
  blocks: [
    {
      kind: "note",
      title: "Build on what you learned",
      text: "Toyota remembered your expense. Now learn how to inspect the work behind her replies. Keep Toyota’s Home conversation open in another tab. This lesson reads existing evidence; its Refresh button never starts an ADW, retries a save, or changes an expense.",
    },
    {
      kind: "step",
      id: "inspect-checkpoint",
      title: "1. Read the checkpoint",
      text: "Click Refresh evidence below. Confirm the training environment and selected expense #900001. Note the latest run ID. The checkpoint is Toyota’s retained place in the workflow; it is separate from your manual checkboxes and is not a new database verification.",
    },
    {
      kind: "workflow-evidence",
      text: "Read Toyota’s current checkpoint, choose an ADW run, and inspect its recorded phases.",
    },
    {
      kind: "step",
      id: "watch-receipt-run",
      title: "2. Ask Toyota to open the supporting information",
      prompt: "Show me the supporting information for expense #900001.",
      text: "Send this in Toyota’s conversation and keep that tab open. Wait until her work panel says the supporting information opened. Return here and click Refresh evidence with Latest run selected. Compare the run ID with the one you noted.",
    },
    {
      kind: "step",
      id: "compare-run-phases",
      title: "3. Inspect the phases and an earlier run",
      text: "Look for load_assignment, operate_tax_visit, and publish_checkpoint. Read the descriptions and timestamps. Choose an earlier run from ADW run to compare its evidence. One conversation request can produce more than one run: requesting browser work and acknowledging its result are separate operations. The current checkpoint remains current even when you select an older run.",
    },
    {
      kind: "step",
      id: "watch-save-evidence",
      title: "4. Connect a category change to its evidence",
      prompt: "Change the category of expense #900001 to Walgreens (RM).",
      text: "Use the category flow you practiced in the first lesson. If the practice expense already has RM, explicitly request Walgreens (RJ) instead. Wait for Toyota’s verified stored-value result. Refresh this viewer, then inspect recent runs. The save run has validate_editor_request, save_through_expense_editor, verify_stored_expense, and publish_edit_evidence. The latest run may instead be the separate acknowledgement. Use the run picker and Open recorded events to inspect the actual evidence.",
    },
    {
      kind: "note",
      title: "What the results mean",
      text: "Completed means a phase recorded success. It does not mean every action was an expense save. No completion recorded means no ending was present in the returned trace; it is not proof that work is still running. A failed read hides prior evidence until Refresh succeeds. This viewer does not automatically poll. Refresh after each request you want to inspect.",
    },
    {
      kind: "text",
      text: "For Web Component practice, inspect <workflow-inspector> and its <workflow-phase> children in Developer Tools. The inspector receives IWorkflowInspector; its session receives IWorkflowEvidenceSource. The dashboard supplies a read-only Adapter over existing ADW routes. The manual’s block registry accepts this new renderer without adding workflow-specific logic to the manual shell.",
    },
  ],
};
