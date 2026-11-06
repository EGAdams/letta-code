import { Gauge } from "./gauge.js";
import { BAND, band, halfDialConfig } from "./half-dial-config.js";

/** Model quota remaining: low is bad. */
export class QuotaLeftGauge extends Gauge {
  constructor(renderTo, Engine) {
    super(
      halfDialConfig(renderTo, {
        units: "% left",
        highlights: [
          band(0, 10, BAND.red),
          band(10, 30, BAND.yellow),
          band(30, 100, BAND.green),
        ],
      }),
      Engine,
    );
  }
}
