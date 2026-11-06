import { Gauge } from "./gauge.js";
import { BAND, band, halfDialConfig } from "./half-dial-config.js";

/** RAM / disk / network use: high is bad. */
export class PercentUsedGauge extends Gauge {
  constructor(renderTo, Engine) {
    super(
      halfDialConfig(renderTo, {
        units: "% used",
        highlights: [
          band(0, 70, BAND.green),
          band(70, 90, BAND.yellow),
          band(90, 100, BAND.red),
        ],
      }),
      Engine,
    );
  }
}
