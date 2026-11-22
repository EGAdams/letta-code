/**
 * Pure rules for whether a model from /api/remediation-models (monitoring/
 * model_registry.py's provider_selection_payload) may be picked for
 * "Execute agent". Gated on `configured` -- whether a real CLI or credential
 * file is present on this host -- not `available`, which model_registry.py
 * deliberately never sets true until an authenticated runtime probe exists.
 * Claude Opus ships with no verification method at all, so it is always
 * "unconfigured" here, with the registry's own explanation why -- never a
 * fabricated "Opus is ready".
 */

/** @param {object|null} provider - one entry of payload.providers, or null if not reported */
export function modelOptionState(provider) {
  if (!provider || typeof provider !== "object") {
    return { enabled: false, reason: "not reported by the model registry" };
  }
  const configured = provider.configured === true;
  const detail = typeof provider.detail === "string" ? provider.detail : "";
  return configured
    ? { enabled: true, reason: detail }
    : { enabled: false, reason: detail || "not configured in this deployment" };
}

/** Finds `id` in a providers array; tolerant of a missing/malformed payload. */
export function pickProvider(providers, id) {
  return (
    (Array.isArray(providers) ? providers : []).find(
      (p) => p && typeof p === "object" && p.id === id,
    ) || null
  );
}
