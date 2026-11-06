import { Gauge } from "./gauge.js";
import { BAND, band, halfDialConfig } from "./half-dial-config.js";

/** Share of a fleet that is up / healthy: anything short of all is a warning. */
export class HealthyRatioGauge extends Gauge {
  constructor(renderTo, Engine) {
    super(
      halfDialConfig(renderTo, {
        units: "% healthy",
        highlights: [
          band(0, 75, BAND.red),
          band(75, 99.9, BAND.yellow),
          band(99.9, 100, BAND.green),
        ],
      }),
      Engine,
    );
  }
}
