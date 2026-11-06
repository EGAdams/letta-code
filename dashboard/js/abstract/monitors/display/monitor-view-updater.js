/**
 * MonitorViewUpdater — Oak Ridge's ViewUpdater for one monitor: set the gauge,
 * then let the display adapter print the same value. Values are clamped into
 * the gauge's own range so an over-range count pins the needle, not breaks it.
 */
export class MonitorViewUpdater {
  constructor(gauge, displayAdapter) {
    this.gauge = gauge;
    this.displayAdapter = displayAdapter;
  }

  updateView(value) {
    const { minValue = 0, maxValue = 100 } = this.gauge.config;
    const shown = Number.isFinite(value)
      ? Math.min(maxValue, Math.max(minValue, value))
      : minValue;
    this.gauge.setValue(shown);
    this.displayAdapter.update(value);
  }
}
