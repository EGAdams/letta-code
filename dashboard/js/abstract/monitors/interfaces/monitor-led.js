/**
 * MonitorLed — the-factory's MonitorLed, driving an SVG LED instead of a div.
 * The colours are the-factory's: RUNNING lightyellow, PASS lightgreen,
 * FAIL #fb6666. `target` is anything with setAttribute (the <monitor-led>).
 */
import { levelLed } from "../levels/level-palette.js";

export const LED_COLORS = Object.freeze({
  RUNNING: "lightyellow",
  PASS: "lightgreen",
  FAIL: "#fb6666",
});

export class MonitorLed {
  constructor(target) {
    this.target = target;
  }

  setRunning() {
    this.setLedBackgroundColor(LED_COLORS.RUNNING);
  }
  setPass() {
    this.setLedBackgroundColor(LED_COLORS.PASS);
  }
  setFail() {
    this.setLedBackgroundColor(LED_COLORS.FAIL);
  }

  /** A monitor level (ok / warn / crit / unknown) as an LED colour. */
  setLevel(level) {
    this.setLedBackgroundColor(levelLed(level));
  }

  setLedBackgroundColor(color) {
    this.target.setAttribute("color", color);
  }

  setLedTextColor(color) {
    this.target.setAttribute("text-color", color);
  }

  /** @param {import("./monitor-led-data.js").MonitorLedData} data */
  setLedText(data) {
    this.target.setAttribute("text", data.ledText);
  }
}
