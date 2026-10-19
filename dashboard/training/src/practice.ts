import type { IManualChapter } from "../../../../the-factory/src/components/training-manual/interfaces";

export const practiceChapter: IManualChapter = {
  id: "first-session",
  title: "Your first practice session",
  summary:
    "One synthetic expense, one category change, and a stored value you can check for yourself.",
  blocks: [
    {
      kind: "note",
      title: "Keep two tabs open",
      text: "Keep this manual open. Use “Open Toyota in another tab” above for the dashboard Home conversation. Keep that dashboard tab open while Toyota operates the editor. Send one request at a time and wait for its result. The sentences below are examples, not magic commands.",
    },
    {
      kind: "step",
      id: "ask-capabilities",
      title: "1. Ask what Toyota can do",
      prompt: "What can you help me do with tax issues?",
      text: "She should describe the installed training operations: selecting the expense, opening supporting information and the editor, applying an explicit category, and checking progress. She should explain the training limitation.",
    },
    {
      kind: "step",
      id: "start-assignment",
      title: "2. Choose the assignment",
      prompt: "Let’s work on tax issues.",
      text: "Look for “Toyota’s work — synthetic training”. Toyota is still your conversational coordinator; the assignment selects the workflow capabilities she uses.",
    },
    {
      kind: "step",
      id: "select-expense",
      title: "3. Locate the practice expense",
      prompt: "Open expense #900001.",
      text: "Confirm #900001, $12.34, “Training pharmacy purchase”. This record lives in the separate rol_receptionist_training database. Its category may be RM or RJ depending on the last practice session.",
    },
    {
      kind: "step",
      id: "inspect-evidence",
      title: "4. Open supporting information",
      prompt: "Show me its supporting information.",
      text: "A practice receipt should appear in Toyota’s browser area. Read the details before deciding what change to request.",
    },
    {
      kind: "step",
      id: "open-editor",
      title: "5. Open the expense editor",
      prompt: "Open its expense editor.",
      text: "Check the record number and current category in the editor. The training flow reuses the application’s expense editor and validation.",
    },
    {
      kind: "step",
      id: "save-category",
      title: "6. Request a specific category and verify it",
      prompt: "Change the category to Walgreens (RM).",
      text: "Watch the work panel while Toyota uses Save Changes and independently reloads the expense. Completion means the panel says “verified” and reports Walgreens (RM). If it already has RM, practice with “Change the category to Walgreens (RJ).” A promise to save is not verification.",
    },
    {
      kind: "step",
      id: "resume-work",
      title: "7. Check that your place is retained",
      prompt: "Which expense are we working on, and what is its category?",
      text: "After the save is verified, refresh the dashboard and ask this question. Expect #900001 and the stored category. The assignment checkpoint should survive the refresh.",
    },
    {
      kind: "note",
      title: "What the checkboxes mean",
      text: "“I tried this step” is your personal practice checklist. It never saves an expense or checks the database. Toyota’s work panel and its independent readback provide the actual save evidence.",
    },
  ],
};
