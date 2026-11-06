import { CountDisplayAdapter } from "./count-display-adapter.js";
import { PercentDisplayAdapter } from "./percent-display-adapter.js";

/** Picks the display Strategy that suits a gauge type. */
const BY_GAUGE = Object.freeze({ AlertCountGauge: CountDisplayAdapter });

export function createDisplayAdapter(gaugeType, element) {
  const Adapter = BY_GAUGE[gaugeType] || PercentDisplayAdapter;
  return new Adapter(element);
}
