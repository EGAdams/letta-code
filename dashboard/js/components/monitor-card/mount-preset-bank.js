/**
 * Puts a <push-button-bank> right after `body` when the source has presets
 * (replacing any earlier one) and returns the preset pressed at start.
 */
export function mountPresetBank(body, source) {
  body.parentNode.querySelector("push-button-bank")?.remove();
  if (!source.presets?.length) return null;
  const bank = document.createElement("push-button-bank");
  bank.presets = source.presets;
  bank.selected = source.preset;
  body.after(bank);
  return source.preset;
}
