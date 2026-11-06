import { alertListDefine } from "./alert-list/index.js";
import { allMonitorsPageDefine } from "./all-monitors-page/index.js";
import { countdownRingDefine } from "./countdown-ring/index.js";
import { monitorCardDefine } from "./monitor-card/index.js";
import { monitorLedDefine } from "./monitor-led/index.js";
import { pushButtonBankDefine } from "./push-button-bank/index.js";
import { radialGaugeViewDefine } from "./radial-gauge-view/index.js";
import { statusDonutDefine } from "./status-donut/index.js";
import { trendSparklineDefine } from "./trend-sparkline/index.js";

/** Registers every element the All Monitors page uses. */
export function defineMonitorComponents() {
  [
    monitorLedDefine,
    radialGaugeViewDefine,
    countdownRingDefine,
    statusDonutDefine,
    trendSparklineDefine,
    pushButtonBankDefine,
    alertListDefine,
    monitorCardDefine,
    allMonitorsPageDefine,
  ].forEach((define) => {
    define();
  });
}
