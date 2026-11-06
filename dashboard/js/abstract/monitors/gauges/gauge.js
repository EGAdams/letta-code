/**
 * Gauge — Oak Ridge's Gauge, unchanged in shape: it wraps one canvas-gauges
 * RadialGauge built from a config. The engine is injectable so tests can run
 * without a canvas; in the page it is the vendored global RadialGauge.
 */
export class Gauge {
  constructor(config, Engine = globalThis.RadialGauge) {
    if (typeof Engine !== "function") {
      throw new Error(
        "RadialGauge is not loaded (vendor/canvas-gauges/gauge.min.js)",
      );
    }
    this.config = config;
    this.gauge = new Engine(this.config);
  }

  draw() {
    this.gauge.draw();
  }
  update(options) {
    this.gauge.update(options);
  }
  setValue(value) {
    this.gauge.value = value;
  }
  getValue() {
    return this.gauge.value;
  }
  getElement() {
    return this.config.renderTo;
  }
  destroy() {
    this.gauge.destroy?.();
  }
}
