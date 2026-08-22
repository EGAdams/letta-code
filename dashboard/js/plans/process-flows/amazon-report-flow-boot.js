import { MermaidView } from "../mermaid-view.js";
import {
  AMAZON_MARKETPLACE_KEY,
  clearAmazonWorkflowFrame,
  loadJanuaryReportOptions,
  paintAmazonWorkflowFrame,
  ReportWorkflowAnimator,
  WORKFLOW_EVENTS,
} from "./amazon-report-workflow.js";

const select = document.getElementById("report-document");
const startButton = document.getElementById("start-processing");
const diagramPanel = document.getElementById("amazon-diagram-panel");
const unavailablePanel = document.getElementById("workflow-unavailable-panel");
const dialog = document.getElementById("workflow-unavailable-dialog");
const dialogOk = document.getElementById("workflow-dialog-ok");
const status = document.getElementById("workflow-status");
const progress = document.getElementById("workflow-progress-bar");
const diagramMount = document.getElementById("diagram-mount");

const mermaidView = new MermaidView({
  mermaid: globalThis.mermaid,
  svgPanZoom: globalThis.svgPanZoom,
});

const code = String.raw`sequenceDiagram
  participant Workbook as Amazon Orders 2025 workbook
  participant Source as AmazonMarketplaceSource
  participant Order as AmazonMarketplaceExpense
  participant Service as AmazonMarketplaceImportService
  participant Stored as StoredAmazonExpense
  participant Repo as AmazonMarketplaceExpenseRepository
  participant DB as MySQL expenses table
  participant Verify as Verification/report builder
  participant HTML as report.html

  Workbook->>Source: Read sharedStrings.xml and sheet1.xml
  Source->>Source: Parse order date, amount, description
  Source->>Order: Create one object per non-empty order
  Note over Workbook,Order: 51 orders · 103 item rows · $1,839.64 itemized total
  Source-->>Service: expenses() returns AmazonMarketplaceExpense objects
  Service->>Stored: Map each order to StoredAmazonExpense
  Service->>Repo: import_expenses(category_id=143)
  Repo->>DB: INSERT one row per order
  Note over Repo,DB: id_light = amazon-order-ORDER_ID · role = STANDALONE
  DB-->>Verify: Return 51 persisted expense rows
  Workbook-->>Verify: Provide 51 order IDs and 103 source item rows
  Verify->>Verify: Match orders to DB rows and sum with Decimal arithmetic
  Verify->>Verify: Check duplicate id_light keys and vendor key amazon_marketplace
  Verify->>Verify: Check category 143 Amazon → Office & Administration
  Verify->>Verify: Check receipt metadata and final PASS status
  Verify->>HTML: Write verified summary and transaction table
  HTML-->>Verify: report.html exists in the January report directory
  HTML-->>Verify: Dashboard embeds the report under Project Plans → ROL Finance → Reports`;

await mermaidView.render(diagramMount, {
  title: "Workbook → database → verification → dashboard report",
  caption:
    "Use the mouse wheel over the SVG to zoom, drag to pan, or use the controls in the lower-right corner.",
  code,
});

const svg = diagramMount.querySelector("svg");

const emit = (type, detail) =>
  document.dispatchEvent(new CustomEvent(type, { detail }));

const animator = new ReportWorkflowAnimator({ emit });

function updateSelection() {
  const available = select.value === AMAZON_MARKETPLACE_KEY;
  animator.cancel();
  if (svg) clearAmazonWorkflowFrame(svg);
  diagramPanel.hidden = !available;
  unavailablePanel.hidden = available;
  startButton.disabled = false;
  startButton.textContent = "Start Processing";
  status.textContent = available
    ? "Ready to replay the Amazon Marketplace report workflow."
    : "Select Start Processing to check workflow availability.";
  progress.style.width = "0%";
}

function showUnavailableDialog() {
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

document.addEventListener(WORKFLOW_EVENTS.start, (event) => {
  startButton.disabled = true;
  select.disabled = true;
  startButton.textContent = "Processing…";
  status.textContent = `Starting 1 of ${event.detail.total}…`;
  progress.style.width = "0%";
});

document.addEventListener(WORKFLOW_EVENTS.step, (event) => {
  const { index, total, step } = event.detail;
  if (svg) paintAmazonWorkflowFrame(svg, step);
  status.textContent = `Step ${index + 1} of ${total}: ${step.label}`;
  progress.style.width = `${((index + 1) / total) * 100}%`;
});

document.addEventListener(WORKFLOW_EVENTS.complete, () => {
  if (svg) clearAmazonWorkflowFrame(svg);
  status.textContent =
    "Processing complete — report.html is available in the dashboard.";
  startButton.disabled = false;
  select.disabled = false;
  startButton.textContent = "Replay Processing";
});

document.addEventListener(WORKFLOW_EVENTS.cancel, () => {
  select.disabled = false;
});

startButton.addEventListener("click", async () => {
  if (select.value !== AMAZON_MARKETPLACE_KEY) {
    showUnavailableDialog();
    return;
  }
  await animator.play();
});

select.addEventListener("change", updateSelection);
dialogOk.addEventListener("click", () => dialog.close());

try {
  const reports = await loadJanuaryReportOptions();
  select.replaceChildren(
    ...reports.map((report) => {
      const option = document.createElement("option");
      option.value = report.key;
      option.textContent = report.label;
      return option;
    }),
  );
  select.value = AMAZON_MARKETPLACE_KEY;
} catch (error) {
  status.textContent = `Could not load January report tabs: ${error.message}`;
  select.replaceChildren();
  for (const [key, label] of [
    ["fnbo-4851", "FNBO 4851"],
    ["amex-personal-year", "Amex 1006"],
    ["bank-5938-pdf1", "Bank 5938 PDF 1"],
    [AMAZON_MARKETPLACE_KEY, "Amazon Marketplace"],
  ]) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = label;
    select.append(option);
  }
  select.value = AMAZON_MARKETPLACE_KEY;
}

updateSelection();
