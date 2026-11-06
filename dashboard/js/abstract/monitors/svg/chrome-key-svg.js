import { esc } from "./svg-escape.js";

export const KEY_W = 56;
export const KEY_PITCH = 62;

/**
 * One chrome push button from a '57 Delco dash radio: a dark slot, the key's
 * top lip (seen when it sticks out), its ribbed chrome face, and a shadow
 * the slot casts once it is pushed in. Both looks are drawn; CSS on
 * [aria-checked] picks one, so pressing it animates instead of redrawing.
 */
export function chromeKeySvg({ key, label }, x, pressed) {
  const ribs = [14, 17, 29, 32]
    .map(
      (y) =>
        `<line class="rib" x1="${x + 6}" x2="${x + KEY_W - 6}" y1="${y}" y2="${y}"/>`,
    )
    .join("");
  return (
    `<g class="key" data-key="${esc(key)}" role="radio" tabindex="${pressed ? 0 : -1}" aria-checked="${pressed}" aria-label="${esc(label)}">` +
    `<rect class="slot" x="${x - 2}" y="4" width="${KEY_W + 4}" height="36" rx="4"/>` +
    `<g class="cap">` +
    `<path class="lip" d="M ${x + 3} 10 L ${x + 6} 5 H ${x + KEY_W - 6} L ${x + KEY_W - 3} 10 Z"/>` +
    `<rect class="face" x="${x}" y="10" width="${KEY_W}" height="26" rx="3"/>` +
    `${ribs}` +
    `<text class="engrave" x="${x + KEY_W / 2}" y="25.5">${esc(label)}</text>` +
    `<text class="label" x="${x + KEY_W / 2}" y="25">${esc(label)}</text>` +
    `</g>` +
    `<rect class="sink" x="${x - 2}" y="4" width="${KEY_W + 4}" height="36" rx="4"/>` +
    `</g>`
  );
}
