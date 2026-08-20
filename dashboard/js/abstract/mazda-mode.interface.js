/**
 * Pure decision logic for the Automatic / Semi-Automatic switch.
 *
 * One switch, one sentence: does Mazda read the NEXT scanned document by
 * herself, or does it wait here for a human to press "Mazda Fill"? Flipping it
 * never re-runs, recalls or re-files anything already dispatched -- it is a
 * preference about the next document, and the label says which of the two
 * worlds you are in rather than what pressing it would do.
 *
 * The wire values are the intake pipeline's own words ("auto" / "human_only",
 * see intake/mazda_mode.py) because every stored intake record, status message
 * and test already says them. Only the operator-facing labels are new. Those
 * labels are mirrored on both sides of the process boundary -- Python renders
 * the initial one into the mount point's data attributes so the switch never
 * paints itself wrong and corrects itself a moment later -- and
 * tests/test_mazda_mode.py reads this file back to pin the two lists together,
 * the same arrangement MAZDA_FILL_MODEL_OPTIONS already uses.
 *
 * No DOM, no fetch -- js/implementation/manual-entry-form.js owns that side.
 */

export const MAZDA_MODE = Object.freeze({
  AUTOMATIC: "auto",
  SEMI_AUTOMATIC: "human_only",
});

export const MAZDA_MODE_LABELS = Object.freeze({
  [MAZDA_MODE.AUTOMATIC]: "Mazda Automatic",
  [MAZDA_MODE.SEMI_AUTOMATIC]: "Mazda Semi-Automatic",
});

/**
 * @typedef {Object} MazdaModeState
 * @property {boolean} ok
 * @property {string} mode        "auto" | "human_only"
 * @property {boolean} automatic
 * @property {string} label       what the switch says right now
 * @property {string} source      "operator" | "default"
 * @property {?string} error
 */

/**
 * The switch's text for a given position.
 *
 * Derived from the boolean rather than read off the response so the label can
 * follow the operator's click immediately, before the server has answered --
 * and then be replaced by the server's own label when it does. The two agree
 * by construction (see MAZDA_MODE_LABELS).
 * @param {boolean} automatic
 * @returns {string}
 */
export function mazdaModeLabel(automatic) {
  return MAZDA_MODE_LABELS[
    automatic ? MAZDA_MODE.AUTOMATIC : MAZDA_MODE.SEMI_AUTOMATIC
  ];
}

/**
 * The initial state, read off the mount point Python rendered.
 *
 * A missing attribute means the page was rendered without a mode stamped, in
 * which case Automatic is the honest guess: it is the pipeline's own default
 * (MAZDA_DECISION_MODE unset -> 'auto'), so showing Semi-Automatic would be
 * claiming Mazda is switched off on a box where she is not. GET /api/mazda-mode
 * answers the same question for anything that renders its own shell without
 * the stamp; the intake report always stamps it.
 * @param {{mazdaAutomatic?: string, mazdaModeLabel?: string}} dataset
 * @returns {MazdaModeState}
 */
export function readMazdaModeDataset(dataset) {
  const source = dataset || {};
  const automatic = source.mazdaAutomatic !== "false";
  return {
    ok: true,
    mode: automatic ? MAZDA_MODE.AUTOMATIC : MAZDA_MODE.SEMI_AUTOMATIC,
    automatic,
    label: source.mazdaModeLabel || mazdaModeLabel(automatic),
    source: "default",
    error: null,
  };
}

/**
 * Body of POST /api/mazda-mode.
 *
 * A boolean, not a mode name: this side holds a checkbox, not the intake
 * pipeline's vocabulary, and a request that can carry an arbitrary word is a
 * request that can carry a typo.
 * @param {boolean} automatic
 */
export function buildMazdaModePayload(automatic) {
  return { automatic: automatic === true };
}

/**
 * Boundary check for GET/POST /api/mazda-mode's response.
 *
 * A malformed or failed answer deliberately reports `ok: false` WITHOUT
 * inventing a position for the switch: the caller puts the switch back where
 * it was and says so, because the one thing worse than a switch that failed to
 * move is a switch showing a mode the server is not actually in.
 * @param {unknown} json
 * @returns {MazdaModeState}
 */
export function readMazdaModeResponse(json) {
  if (typeof json !== "object" || json === null) {
    return {
      ok: false,
      mode: "",
      automatic: false,
      label: "",
      source: "",
      error: "malformed response",
    };
  }
  const mode = typeof json.mode === "string" ? json.mode : "";
  const known =
    mode === MAZDA_MODE.AUTOMATIC || mode === MAZDA_MODE.SEMI_AUTOMATIC;
  return {
    ok: json.ok === true && known,
    mode: known ? mode : "",
    automatic: json.automatic === true,
    label: typeof json.label === "string" ? json.label : "",
    source: typeof json.source === "string" ? json.source : "",
    error:
      typeof json.error === "string"
        ? json.error
        : known
          ? null
          : "malformed response",
  };
}

/**
 * What the status line says after the switch moves.
 *
 * States the scope out loud every time. "Automatic" sounds retroactive, and an
 * operator who believes the document already on screen is about to be filed
 * for them will wait for something that is never going to happen.
 * @param {MazdaModeState} state
 */
export function summarizeMazdaMode(state) {
  if (!state.ok) {
    return `Could not change the mode: ${state.error || "unknown error"}. The switch was put back.`;
  }
  return state.automatic
    ? `${state.label}: Mazda reads and files the next scanned document herself. This one is unchanged.`
    : `${state.label}: the next scanned document waits here for a human. Press Mazda Fill to have her read it.`;
}
