// finance-nav.js — ROL Finance and its two child navs (Reports, Scanners).
//
// The Reports sub-nav's tabs are injected dynamically by
// RolFinanceReportsController, so it uses event delegation; the controller
// keeps the open month and the open document highlighted independently.

import { openScannerReportTab } from "./scanner-report-tab.js";

export function bindFinanceNav({ doc, http, nav, viewNav, RF, AM, scanners }) {
  const setFinanceTab = (tab) =>
    viewNav.setActive(
      nav.rolFinance,
      '[data-nav="rol-finance"][data-target]',
      tab,
    );

  const openFreezerScanner = () => {
    const freezerTab = nav.scanners.querySelector(
      '[data-nav="scanners"][data-target="scanners-freezer"]',
    );
    if (freezerTab)
      viewNav.setActive(
        nav.scanners,
        '[data-nav="scanners"][data-target]',
        freezerTab,
      );
    viewNav.activateView("scanners-freezer");
    scanners.controllers.freezer?.startMonitor();
    scanners.controllers.freezer?.refreshDiagnostics();
  };

  // ROL Finance sub-nav (Current Status / Taxes / Reports / Scanners)
  nav.rolFinance
    .querySelectorAll('[data-nav="rol-finance"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        setFinanceTab(tab);
        if (tab.dataset.target === "rol-finance-reports") {
          nav.rolFinance.classList.add("hidden");
          nav.rolFinanceReports.classList.remove("hidden");
          RF.openReports().then(() => RF.refreshStatus());
          return;
        }
        if (tab.dataset.target === "rol-finance-scanners") {
          nav.rolFinance.classList.add("hidden");
          nav.scanners.classList.remove("hidden");
          openFreezerScanner();
          return;
        }
        viewNav.activateView(tab.dataset.target);
      });
    });

  // Month tabs switch the document list (Jan/Feb 2025); report tabs open a
  // single document.
  nav.rolFinanceReports.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.id === "btn-back-rol-finance-reports") return;
    if (tab.dataset.recentReport) {
      RF.openRecentReport();
      return;
    }
    if (tab.dataset.scanner) {
      RF.openScannerReport(tab.dataset.scanner);
      return;
    }
    if (tab.dataset.monthKey) {
      RF.openMonth(tab.dataset.monthKey).then(() => RF.refreshStatus());
      return;
    }
    if (tab.dataset.reportKey) {
      RF.selectReport(tab.dataset.reportKey);
    }
  });

  // ROL Finance Scanners sub-nav (Freezer / Window / Vendor Review / reports).
  nav.scanners
    .querySelectorAll('[data-nav="scanners"][data-target]')
    .forEach((tab) => {
      tab.addEventListener("click", () => {
        viewNav.setActive(
          nav.scanners,
          '[data-nav="scanners"][data-target]',
          tab,
        );
        viewNav.activateView(tab.dataset.target);
        // Only poll the scanner whose tab is showing.
        scanners.stopAllMonitors();
        if (tab.dataset.target === "scanners-freezer") {
          scanners.controllers.freezer?.startMonitor();
          scanners.controllers.freezer?.refreshDiagnostics();
        }
        if (tab.dataset.target === "scanners-window") {
          scanners.controllers.window?.refreshDiagnostics();
        }
        if (tab.dataset.target === "scanners-vendor-review") {
          scanners.vendorReview?.refresh();
        }
        if (tab.dataset.scannerReport) {
          openScannerReportTab({ doc, http, tab, RF, AM });
        }
      });
    });

  doc
    .getElementById("btn-back-rol-finance")
    ?.addEventListener("click", () => viewNav.returnToHome(nav.rolFinance));

  // Reports backs out one level, to the ROL Finance sub-nav.
  doc
    .getElementById("btn-back-rol-finance-reports")
    ?.addEventListener("click", () => {
      nav.rolFinanceReports.classList.add("hidden");
      nav.rolFinance.classList.remove("hidden");
      const reportsTab = nav.rolFinance.querySelector(
        '[data-nav="rol-finance"][data-target="rol-finance-reports"]',
      );
      if (reportsTab) setFinanceTab(reportsTab);
      viewNav.activateView("rol-finance-reports");
    });

  doc.getElementById("btn-back-scanners")?.addEventListener("click", () => {
    scanners.stopAllMonitors();
    nav.scanners.classList.add("hidden");
    nav.rolFinance.classList.remove("hidden");
    const planTab = nav.rolFinance.querySelector(
      '[data-nav="rol-finance"][data-target="rol-finance-plan"]',
    );
    if (planTab) setFinanceTab(planTab);
    viewNav.activateView("rol-finance-plan");
  });
}
