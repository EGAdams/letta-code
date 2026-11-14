// Layout arithmetic for the sequence diagram. Pure: no DOM, no Vue.
//
// x positions are percentages of the plot width, so the diagram stretches with
// the Terminal tab; y positions are pixels from the top of the diagram body,
// one fixed-height row per message, as in a Mermaid sequence diagram.

/** Width of the time axis on the left, in px. */
export const AXIS_WIDTH = 78;
/** Narrowest a participant column may get before the diagram scrolls sideways. */
export const COLUMN_MIN_WIDTH = 170;
/** Height of one message row, in px. */
export const ROW_HEIGHT = 40;
/** Space above the first and below the last message row, in px. */
export const BODY_PADDING = 22;
/** Half the extra length an activation bar gets above its first and below its last row. */
export const BAR_OVERHANG = 11;

/** Centre of column `index` of `count`, as a percentage of the plot width. */
export function columnCentre(index: number, count: number): number {
  return ((index + 0.5) / Math.max(1, count)) * 100;
}

/** Share of the plot width one column takes, in percent. */
export function columnShare(count: number): number {
  return 100 / Math.max(1, count);
}

/** y of the arrow line in row `row`, in px from the top of the body. */
export function rowY(row: number): number {
  return BODY_PADDING + row * ROW_HEIGHT + ROW_HEIGHT * 0.62;
}

/** Height of a body holding `rows` message rows (an empty body still shows its lifelines). */
export function bodyHeight(rows: number): number {
  return BODY_PADDING * 2 + Math.max(1, rows) * ROW_HEIGHT;
}

export interface BarSpan {
  top: number;
  height: number;
}

/**
 * An activation bar from row `from` to row `to`; `to === null` means still open,
 * so the bar runs to the bottom of the body.
 */
export function barSpan(
  from: number,
  to: number | null,
  rows: number,
): BarSpan {
  const top = rowY(from) - BAR_OVERHANG;
  const bottom =
    to === null
      ? bodyHeight(rows) - BODY_PADDING / 2
      : rowY(Math.max(from, to)) + BAR_OVERHANG;
  return { top, height: Math.max(BAR_OVERHANG * 2, bottom - top) };
}

export type Direction = "right" | "left" | "self";

export function direction(from: number, to: number): Direction {
  return from === to ? "self" : from < to ? "right" : "left";
}
