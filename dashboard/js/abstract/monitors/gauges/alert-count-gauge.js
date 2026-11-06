import { Gauge } from "./gauge.js";
import { BAND, band, halfDialConfig } from "./half-dial-config.js";

/** Open alerts / failures: zero is the only green. */
export class AlertCountGauge extends Gauge {
  constructor(renderTo, Engine) {
    super(
      halfDialConfig(renderTo, {
        units: "alerts",
        maxValue: 10,
        majorTicks: ["0", "2", "4", "6", "8", "10+"],
        minorTicks: 2,
        highlights: [
          band(0, 0.5, BAND.green),
          band(0.5, 3, BAND.yellow),
          band(3, 10, BAND.red),
        ],
      }),
      Engine,
    );
  }
}
