import type { IManualChapter } from "../../../../the-factory/src/components/training-manual/interfaces";

export const architectureChapters: readonly IManualChapter[] = [
  {
    id: "web-components",
    title: "Learn the Web Components",
    summary:
      "Nine custom elements turn this manual into a reusable example from the-factory library.",
    blocks: [
      {
        kind: "text",
        text: "A Web Component gives a custom HTML element its own behavior and presentation. This manual uses the same @Component decorator and wrap() registration helper as the existing library. Each component has its own folder, TypeScript class, HTML template, observed attributes, index.ts, and styles/ directory.",
      },
      { kind: "command", text: "<training-manual></training-manual>" },
      {
        kind: "text",
        text: "The second lesson adds workflow-inspector for read-only checkpoint and run inspection, and workflow-phase for each recorded phase. Neither component knows Toyota’s endpoint URLs. The app injects the evidence source through interfaces and provides its own link through a slot.",
      },
      {
        kind: "text",
        text: "training-manual coordinates the page. manual-toc handles chapter links. manual-chapter presents a lesson. manual-progress displays practice progress. training-step supplies a reversible checkbox. command-example presents copyable text. training-callout highlights guidance or unfinished features.",
      },
      {
        kind: "command",
        text: '<training-step step-id="inspect" heading="Inspect the receipt" text="Read the supporting facts.">\n    <command-example example="Show me its supporting information."></command-example>\n</training-step>',
      },
      {
        kind: "text",
        text: "Attributes carry simple values such as heading and completed. A slot places child content inside a component’s template. The shadow root keeps the template and styles local. Open browser Developer Tools → Elements and expand a custom element’s #shadow-root to inspect it.",
      },
      {
        kind: "note",
        title: "Trace one interaction",
        text: "A checkbox emits manual-complete with its step ID and checked value. The event bubbles through the component boundary. The manual asks IManualSession to update reading progress, then refreshes the progress component. No financial endpoint participates.",
      },
    ],
  },
  {
    id: "interfaces-and-patterns",
    title: "Interfaces and GoF patterns",
    summary:
      "An interface describes the job. The composition root chooses the object that performs it.",
    blocks: [
      {
        kind: "command",
        text: "interface IReadingStore {\n    read( key: string ): unknown;\n    write( key: string, checkpoint: IReadingCheckpoint ): void;\n}",
      },
      {
        kind: "text",
        text: "ManualSession accepts IReadingStore. It does not import localStorage. BrowserReadingStore is an Adapter that satisfies this interface; tests inject an in-memory store or a failing store. The same session logic works with each implementation.",
      },
      {
        kind: "text",
        text: "IChapterNavigation separates bookmarks and browser history from the manual. IClipboard separates copying from example presentation. IBlockRenderer and IBlockFactory separate a content block’s meaning from the Web Component used to display it.",
      },
      {
        kind: "text",
        text: "Registry Factory: ManualBlockFactory selects a registered IBlockRenderer by kind. Composite: the manual contains chapters, and chapters contain blocks such as steps and callouts. Observer: components publish events; the manual reacts. Mediator: TrainingManual coordinates its components. Template Method: ManualComponent supplies the lifecycle contract while each component implements render().",
      },
      {
        kind: "command",
        text: "interface AssignmentPolicies {\n    installed(): readonly string[];\n    for_assignment( name: string ): AssignmentPolicy;\n}",
      },
      {
        kind: "text",
        text: "Strategy registry: the same shape decides what Toyota will accept. On her side InstalledPolicies maps an assignment name to the policy that validates its requests; in the workflow it is AssignmentRegistry, which maps the same name to the Assignment that performs the work. An assignment is declared by being put in one of those maps at a composition root, and nowhere else.",
      },
      {
        kind: "text",
        text: "Both registries refuse a name they do not hold, and the refusal lists what is installed instead of failing silently. The sentence Toyota speaks about which assignments exist is generated from installed(), so it cannot keep advertising something that was removed from the composition root. Today both maps hold one entry: tax_issues.",
      },
      {
        kind: "note",
        title: "Where construction belongs",
        text: "dashboard/training/src/main.ts is the composition root. It chooses browser adapters and the block factory, then injects them through IManualDependencies. The library is under /home/adamsl/the-factory/src/components; ROL-specific lesson data stays in dashboard/training/src.",
      },
      {
        kind: "text",
        text: "To add a chapter, add an IManualChapter to the content catalog with a stable, unique ID. The TOC, search, bookmark, and Previous/Next controls follow the catalog automatically. To add a new visual block, implement IBlockRenderer and register it with the factory. Write its tests before its implementation.",
      },
      {
        kind: "command",
        text: "cd /home/adamsl/letta-code/dashboard/training\nbun run test\nbun run typecheck\nbun run build\nbun run test:browser",
      },
    ],
  },
];
