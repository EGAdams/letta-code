import { getAvailableModelHandles } from "./available-models";
import { getServerUrl } from "./client";
import { getDefaultModel, resolveModel } from "./model";

export const AUTO_MODEL_HANDLE = "letta/auto";
export const AUTO_FAST_MODEL_HANDLE = "letta/auto-fast";

type ModelListClient = {
  models?: {
    list: () => Promise<Array<{ handle?: string | null }>>;
  };
};

function normalizeModelHandle(model?: string): string | undefined {
  if (typeof model !== "string" || model.trim().length === 0) {
    return undefined;
  }

  return resolveModel(model.trim()) ?? model.trim();
}

export function isSelfHostedServer(serverUrl = getServerUrl()): boolean {
  return !serverUrl.includes("api.letta.com");
}

export function isAutoModelHandle(handle?: string | null): boolean {
  return handle === AUTO_MODEL_HANDLE || handle === AUTO_FAST_MODEL_HANDLE;
}

export const FREE_TIER_MODEL_HANDLE = "letta/letta-free";

export function isFreeTierModelHandle(handle?: string | null): boolean {
  return handle === FREE_TIER_MODEL_HANDLE;
}

export function selectDefaultAgentModel(params: {
  preferredModel?: string;
  fallbackModel?: string;
  isSelfHosted: boolean;
  availableHandles?: Iterable<string>;
  disallowedHandles?: Iterable<string>;
  disallowedHandlePrefixes?: Iterable<string>;
}): string | undefined {
  const {
    preferredModel,
    fallbackModel,
    isSelfHosted,
    availableHandles,
    disallowedHandles,
    disallowedHandlePrefixes,
  } = params;
  const resolvedPreferred = normalizeModelHandle(preferredModel);
  const resolvedFallback = normalizeModelHandle(fallbackModel);
  const blockedHandles = new Set(disallowedHandles ?? []);
  // Handle prefixes for providers that are known-broken on this server (e.g. a
  // base provider backed by a stale/dead API key). Such handles still appear in
  // the model list but must never be auto-selected as a default/quota fallback.
  // Mirrors the letta/letta-free special-case (incident 2026-07-04) and the dead
  // base google_ai key incident (2026-08-02, working key lives on BYOK lc-gemini).
  const blockedPrefixes = Array.from(disallowedHandlePrefixes ?? []).filter(
    (prefix) => typeof prefix === "string" && prefix.length > 0,
  );
  const hasBlockedPrefix = (handle: string): boolean =>
    blockedPrefixes.some((prefix) => handle.startsWith(prefix));
  const canUse = (handle?: string): handle is string =>
    typeof handle === "string" &&
    handle.length > 0 &&
    !blockedHandles.has(handle) &&
    !hasBlockedPrefix(handle);

  if (!isSelfHosted) {
    return canUse(resolvedPreferred) ? resolvedPreferred : resolvedFallback;
  }

  const handles = availableHandles
    ? Array.from(
        new Set(
          Array.from(availableHandles).filter(
            (handle): handle is string =>
              typeof handle === "string" && handle.length > 0,
          ),
        ),
      ).filter(
        (handle) => !blockedHandles.has(handle) && !hasBlockedPrefix(handle),
      )
    : null;

  if (handles && handles.length > 0) {
    if (canUse(resolvedPreferred) && handles.includes(resolvedPreferred)) {
      return resolvedPreferred;
    }

    // letta/letta-free is a last resort: on self-hosted servers it is backed
    // by whatever OPENAI_API_KEY the server happens to have, which may be
    // missing or stale, so real provider handles are always preferred.
    const firstNonAutoNonFreeHandle = handles.find(
      (handle) => !isAutoModelHandle(handle) && !isFreeTierModelHandle(handle),
    );
    if (firstNonAutoNonFreeHandle) {
      return firstNonAutoNonFreeHandle;
    }

    const firstNonAutoHandle = handles.find(
      (handle) => !isAutoModelHandle(handle),
    );
    if (firstNonAutoHandle) {
      return firstNonAutoHandle;
    }

    const defaultHandle = getDefaultModel();
    if (handles.includes(defaultHandle)) {
      return defaultHandle;
    }

    return handles[0];
  }

  if (canUse(resolvedPreferred) && !isAutoModelHandle(resolvedPreferred)) {
    return resolvedPreferred;
  }

  if (canUse(resolvedFallback)) {
    return resolvedFallback;
  }

  return undefined;
}

export async function resolveDefaultAgentModel(params: {
  preferredModel?: string;
  fallbackModel?: string;
  availableHandles?: Iterable<string>;
  disallowedHandles?: Iterable<string>;
  disallowedHandlePrefixes?: Iterable<string>;
  serverUrl?: string;
  client?: ModelListClient;
}): Promise<string | undefined> {
  const {
    preferredModel,
    fallbackModel,
    availableHandles,
    disallowedHandles,
    disallowedHandlePrefixes,
    serverUrl,
    client,
  } = params;
  const isSelfHosted = isSelfHostedServer(serverUrl);

  if (availableHandles) {
    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted,
      availableHandles,
      disallowedHandles,
      disallowedHandlePrefixes,
    });
  }

  if (!isSelfHosted) {
    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted: false,
      disallowedHandles,
      disallowedHandlePrefixes,
    });
  }

  try {
    const handles =
      client?.models !== undefined
        ? new Set(
            (await client.models.list())
              .map((model) => model.handle)
              .filter((handle): handle is string => typeof handle === "string"),
          )
        : (await getAvailableModelHandles()).handles;

    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted: true,
      availableHandles: handles,
      disallowedHandles,
      disallowedHandlePrefixes,
    });
  } catch {
    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted: true,
      disallowedHandles,
      disallowedHandlePrefixes,
    });
  }
}

/**
 * The provider segment of a model handle, e.g.
 * "chatgpt-plus-pro/gpt-5.4" -> "chatgpt-plus-pro/". Returns undefined for a
 * handle with no provider segment (no "/", or a leading "/").
 */
export function providerPrefixOfHandle(
  handle?: string | null,
): string | undefined {
  if (typeof handle !== "string") {
    return undefined;
  }
  const slash = handle.indexOf("/");
  if (slash <= 0) {
    return undefined;
  }
  return handle.slice(0, slash + 1);
}

/**
 * Handle prefixes a quota fallback must never select:
 *  1. Server-configured dead providers (`disabledModelHandlePrefixes` — e.g. a
 *     base provider backed by a stale/dead API key that still lists models).
 *  2. The current model's own provider — a quota/rate-limit is account-scoped,
 *     so a sibling model on the same provider would just re-hit the same limit;
 *     the fallback must escape to a different provider.
 */
export function quotaFallbackDisallowedPrefixes(params: {
  currentModelLabel?: string | null;
  configuredDisabledPrefixes?: Iterable<string>;
}): string[] {
  const { currentModelLabel, configuredDisabledPrefixes } = params;
  const currentProviderPrefix = providerPrefixOfHandle(currentModelLabel);
  return Array.from(
    new Set(
      [
        ...Array.from(configuredDisabledPrefixes ?? []),
        ...(currentProviderPrefix ? [currentProviderPrefix] : []),
      ].filter((prefix) => typeof prefix === "string" && prefix.length > 0),
    ),
  );
}

/**
 * Resolve the model to temporarily switch to when the current model hits a
 * quota limit. Prefers Auto, never re-selects the current model or any
 * off-limits provider (see `quotaFallbackDisallowedPrefixes`). Owns the whole
 * quota-fallback selection policy so the UI just calls it.
 */
export async function resolveQuotaFallbackModel(params: {
  currentModelLabel?: string | null;
  configuredDisabledPrefixes?: Iterable<string>;
  availableHandles?: Iterable<string>;
  serverUrl?: string;
  client?: ModelListClient;
}): Promise<string | undefined> {
  const {
    currentModelLabel,
    configuredDisabledPrefixes,
    availableHandles,
    serverUrl,
    client,
  } = params;
  return resolveDefaultAgentModel({
    preferredModel: AUTO_MODEL_HANDLE,
    disallowedHandles: currentModelLabel ? [currentModelLabel] : [],
    disallowedHandlePrefixes: quotaFallbackDisallowedPrefixes({
      currentModelLabel,
      configuredDisabledPrefixes,
    }),
    availableHandles,
    serverUrl,
    client,
  });
}
