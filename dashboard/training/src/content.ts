import type { IManualDocument } from "../../../../the-factory/src/components/training-manual/interfaces";
import { architectureChapters } from "./architecture";
import { practiceChapter } from "./practice";
import { recoveryPracticeChapter } from "./recovery-practice";
import { watchARunChapter } from "./watch-a-run";
import { workPanelChapter } from "./work-panel";

export const trainingManual: IManualDocument = {
  id: "rol-receptionist",
  version: 1,
  title: "ROL Finance training",
  chapters: [
    {
      id: "start-here",
      title: "Start here",
      summary:
        "A hands-on guide to Toyota, ADWs, and the components that make this manual work.",
      blocks: [
        {
          kind: "note",
          title: "Available now · synthetic training",
          text: "Toyota can work with practice expense #900001, open its receipt and editor, apply a category you specify, and verify the stored value. This first lesson uses the separate training database. Real expense editing through the receptionist is still {to_be_implemented}.",
        },
        {
          kind: "text",
          text: "Use Contents to jump to a chapter. Search filters the chapter list using headings, explanations, and example commands. Previous chapter and Next chapter guide you through the full manual. The chapter in the URL can be bookmarked or shared.",
        },
        {
          kind: "text",
          text: "Your reading position and practice checkmarks stay in this browser. They are separate from Toyota’s saved assignment. Reset practice checkmarks clears only the checklist. Copy example copies text; it never sends an instruction or executes a console command.",
        },
        {
          kind: "text",
          text: "Start with “Your first practice session”. Later chapters explain ADWs, the console menu, recovery, Web Components, and interfaces. Features we have not built are explicitly marked {to_be_implemented}.",
        },
        {
          kind: "link",
          text: "Open Toyota’s dashboard Home in another tab ↗",
          href: "/",
        },
      ],
    },
    practiceChapter,
    watchARunChapter,
    workPanelChapter,
    {
      id: "adws-phases-runs",
      title: "ADWs, phases, and runs",
      summary:
        "The workflow is the recipe. A phase is a named step. A run is one execution with evidence.",
      blocks: [
        {
          kind: "text",
          text: "An ADW is an AI Developer Workflow. It defines an operation as named phases. A phase can be ordinary code; it does not have to call a model. A run is one execution of an ADW, with its own ID, events, and results. One conversation can produce several runs.",
        },
        {
          kind: "note",
          title: "Follow the evidence",
          text: "Use “Latest ADW run” in Toyota’s work panel to inspect a run. Its ID identifies that execution. A completed conversation reply does not by itself prove that a database change succeeded; the save flow also reads back the stored expense.",
        },
        {
          kind: "text",
          text: "adw_receptionist_tax.py performs load_assignment → operate_tax_visit → publish_checkpoint. It restores the current assignment, performs a requested operation through shared interfaces, and retains the result. Browser actions may remain pending until the open dashboard carries them out.",
        },
        {
          kind: "text",
          text: "adw_receptionist_edit.py performs validate_editor_request → save_through_expense_editor → verify_stored_expense → publish_edit_evidence. These are code phases. The editor applies normal validation and save behavior; the verification phase independently reloads the expense.",
        },
        {
          kind: "text",
          text: "Toyota is the conversational coordinator. Tools perform bounded operations. An assignment determines the workflow in use. A specialist agent is useful for substantial independent analysis; a routine edit or navigation step can use a tool directly.",
        },
      ],
    },
    {
      id: "console-menu",
      title: "The existing console menu",
      summary:
        "The console and receptionist reuse tax-review behavior, while their user interfaces differ.",
      blocks: [
        {
          kind: "command",
          text: "cd /home/adamsl/rol_finances\njust tax-issues",
        },
        {
          kind: "text",
          text: "The justfile recipe is named tax-issues, with a hyphen. It invokes the resolver shown below. This is the existing real tax-review console, separate from the synthetic receptionist lesson. Copying this example does not execute it.",
        },
        {
          kind: "command",
          text: "tax-issues:\n    uv run adws/adw_resolve_tax_issues.py --config {{config}}",
        },
        {
          kind: "text",
          text: "The shared TaxReviewSession facade provides review questions, category eligibility, and supporting context. The receptionist invokes structured operations through application interfaces. Its training path does not type fixed menu numbers into a terminal.",
        },
        {
          kind: "placeholder",
          title: "Interactive console control by Toyota",
          text: "{to_be_implemented} — general terminal sessions, prompt recognition, retained interactive input, and cancellation through the receptionist.",
        },
      ],
    },
    {
      id: "voice-and-assignments",
      title: "Voice and assignments",
      summary:
        "Learn the workflow with text first, then use the dashboard’s existing voice input.",
      blocks: [
        {
          kind: "text",
          text: "The dashboard already has voice capture and a conversation path to Toyota. A spoken instruction must reach her as a transcript before she can act on it. For the first lesson, type the examples so you can inspect exactly what was requested. Then try the same requests through the existing voice controls and check the transcript.",
        },
        {
          kind: "text",
          text: "“Let’s work on tax issues” selects the assignment without rewriting Toyota’s entire persona. The retained checkpoint includes the assignment, selected expense, progress, and unfinished browser operation. Keep the dashboard open while it processes browser work.",
        },
        {
          kind: "note",
          title: "Use an exact requested change",
          text: "Say the expense number when choosing a record and the complete category name when changing it. If several records or categories could match, clarify the target. Toyota should ask rather than invent a record or a category.",
        },
        {
          kind: "placeholder",
          title: "A complete voice-only lesson",
          text: "{to_be_implemented} — a tested voice-only walkthrough, including microphone setup, transcription correction, interruption, and recovery on each supported device.",
        },
      ],
    },
    {
      id: "recovery",
      title: "Pause, resume, and recover",
      summary:
        "Use the retained checkpoint and stored evidence to decide what to do next.",
      blocks: [
        { kind: "command", text: "Pause this work." },
        {
          kind: "text",
          text: "Pause retains your place. To return, ask to work on tax issues and ask where you left off. Cancellation stops pending work, but it does not undo a category that was already saved.",
        },
        { kind: "command", text: "Where did we leave off?" },
        {
          kind: "note",
          title: "After a stalled or interrupted save",
          text: "Read Toyota’s work panel. If offered, use “Check interrupted operation” to reconcile the saved result before repeating the request. Do not assume that a lost reply means the save failed. Report success only when the stored value is verified.",
        },
        {
          kind: "text",
          text: "If Toyota describes only her old analyst roster, refresh the dashboard and ask what she can do with tax issues. The operational training path needs the receptionist-team service. If that service is unavailable, the fallback conversation does not gain these operations automatically.",
        },
      ],
    },
    recoveryPracticeChapter,
    ...architectureChapters,
    {
      id: "coming-next",
      title: "What is coming next",
      summary:
        "The following capabilities are planned. They are not instructions you can complete today.",
      blocks: [
        {
          kind: "placeholder",
          title: "Real expense assignments",
          text: "{to_be_implemented} — move the verified training interaction to explicitly selected real records.",
        },
        {
          kind: "placeholder",
          title: "Additional assignments",
          text: "{to_be_implemented} — register and demonstrate another assignment, including switching away and restoring unfinished work.",
        },
        {
          kind: "placeholder",
          title: "General browser operations",
          text: "{to_be_implemented} — arbitrary pages, selected sections, and additional requested expense fields beyond this category lesson.",
        },
        {
          kind: "placeholder",
          title: "File and console operations",
          text: "{to_be_implemented} — receptionist file searches, opening results, and maintained interactive terminal sessions.",
        },
        {
          kind: "placeholder",
          title: "Voice training across devices",
          text: "{to_be_implemented} — device-specific voice lessons and verified recovery after speech interruptions.",
        },
      ],
    },
  ],
};
