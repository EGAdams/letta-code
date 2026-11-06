import { AlertCountGauge } from "./alert-count-gauge.js";
import { GaugeRegistry } from "./gauge-registry.js";
import { HealthyRatioGauge } from "./healthy-ratio-gauge.js";
import { PercentUsedGauge } from "./percent-used-gauge.js";
import { QuotaLeftGauge } from "./quota-left-gauge.js";

/**
 * GaugeFactory — Oak Ridge's static createGauge(type), backed by a registry.
 * This module is the only place that names the concrete gauge classes.
 */
export const gaugeRegistry = new GaugeRegistry()
  .register("PercentUsedGauge", PercentUsedGauge)
  .register("QuotaLeftGauge", QuotaLeftGauge)
  .register("HealthyRatioGauge", HealthyRatioGauge)
  .register("AlertCountGauge", AlertCountGauge);

// biome-ignore lint/complexity/noStaticOnlyClass: the public GaugeFactory.createGauge shape is kept
export class GaugeFactory {
  static createGauge(type, renderTo, Engine) {
    return gaugeRegistry.create(type, renderTo, Engine);
  }
}
