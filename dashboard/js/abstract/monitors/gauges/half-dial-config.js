/**
 * The compact half-dial every monitor gauge shares — Oak Ridge's YawGauge
 * config (startAngle 90, ticksAngle 180, arrow needle, no value box), sized
 * for a card. Subclasses pass only ticks, highlights and units.
 */
export function halfDialConfig(renderTo, overrides = {}) {
  return {
    renderTo,
    width: 220,
    height: 130,
    units: "",
    minValue: 0,
    maxValue: 100,
    majorTicks: ["0", "20", "40", "60", "80", "100"],
    minorTicks: 5,
    strokeTicks: true,
    colorPlate: "#fff",
    colorMajorTicks: "#212121",
    colorMinorTicks: "#757575",
    colorNumbers: "#212121",
    highlights: [],
    valueBox: false,
    borders: false,
    needleType: "arrow",
    needleWidth: 4,
    needleCircleSize: 7,
    needleCircleOuter: true,
    needleCircleInner: false,
    animationRule: "linear",
    animationDuration: 300,
    value: 0,
    startAngle: 90,
    ticksAngle: 180,
    ...overrides,
  };
}

/** Oak Ridge's green / yellow / red highlight bands. */
export const BAND = Object.freeze({
  green: "rgba(0, 255, 0, .8)",
  yellow: "rgba(255, 255, 0, .6)",
  red: "rgba(255, 0, 0, .8)",
});

export const band = (from, to, color) => ({ from, to, color });
