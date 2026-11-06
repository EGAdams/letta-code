import { describe, expect, test } from "bun:test";
import { CountDisplayAdapter } from "../abstract/monitors/display/count-display-adapter.js";
import { DisplayAdapter } from "../abstract/monitors/display/display-adapter.js";
import { MonitorViewUpdater } from "../abstract/monitors/display/monitor-view-updater.js";
import { PercentDisplayAdapter } from "../abstract/monitors/display/percent-display-adapter.js";
import { Gauge } from "../abstract/monitors/gauges/gauge.js";
import {
  GaugeFactory,
  gaugeRegistry,
} from "../abstract/monitors/gauges/gauge-factory.js";

class FakeRadialGauge {
  constructor(config) {
    this.config = config;
    this.value = config.value;
    this.drawn = 0;
  }
  draw() {
    this.drawn += 1;
    return this;
  }
  update(options) {
    Object.assign(this.config, options);
  }
}

describe("gauges", () => {
  test("GaugeFactory builds Oak Ridge half-dials by type", () => {
    const g = GaugeFactory.createGauge(
      "PercentUsedGauge",
      "c1",
      FakeRadialGauge,
    );
    g.draw();
    expect(g.gauge.drawn).toBe(1);
    expect(g.getElement()).toBe("c1");
    expect(g.config.startAngle).toBe(90);
    expect(g.config.ticksAngle).toBe(180);
    expect(g.config.highlights.at(-1).color).toBe("rgba(255, 0, 0, .8)");
  });

  test("unknown types throw like Oak Ridge's switch default", () => {
    expect(() =>
      GaugeFactory.createGauge("Nope", "c", FakeRadialGauge),
    ).toThrow("Invalid gauge type");
  });

  test("the registry is open for new types", () => {
    class TinyGauge extends Gauge {
      constructor(to, E) {
        super({ renderTo: to }, E);
      }
    }
    gaugeRegistry.register("TinyGauge", TinyGauge);
    expect(
      GaugeFactory.createGauge("TinyGauge", "x", FakeRadialGauge),
    ).toBeInstanceOf(TinyGauge);
  });

  test("a missing engine is a clear error", () => {
    expect(() => new Gauge({}, undefined)).toThrow("RadialGauge is not loaded");
  });

  test("view updater clamps the needle but reports the real value", () => {
    const gauge = GaugeFactory.createGauge(
      "AlertCountGauge",
      "c",
      FakeRadialGauge,
    );
    const el = { textContent: "" };
    new MonitorViewUpdater(gauge, new CountDisplayAdapter(el)).updateView(14);
    expect(gauge.getValue()).toBe(10);
    expect(el.textContent).toBe("14");
  });

  test("display adapters", () => {
    const el = { textContent: "" };
    new PercentDisplayAdapter(el).update(41.6);
    expect(el.textContent).toBe("42%");
    new PercentDisplayAdapter(el).update(null);
    expect(el.textContent).toBe("—");
    expect(() => new DisplayAdapter().update(1)).toThrow("abstract");
  });
});
