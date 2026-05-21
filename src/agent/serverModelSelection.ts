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

export function selectDefaultAgentModel(params: {
  preferredModel?: string;
  fallbackModel?: string;
  isSelfHosted: boolean;
  availableHandles?: Iterable<string>;
  disallowedHandles?: Iterable<string>;
}): string | undefined {
  const {
    preferredModel,
    fallbackModel,
    isSelfHosted,
    availableHandles,
    disallowedHandles,
  } = params;
  const resolvedPreferred = normalizeModelHandle(preferredModel);
  const resolvedFallback = normalizeModelHandle(fallbackModel);
  const blockedHandles = new Set(disallowedHandles ?? []);
  const canUse = (handle?: string): handle is string =>
    typeof handle === "string" &&
    handle.length > 0 &&
    !blockedHandles.has(handle);

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
      ).filter((handle) => !blockedHandles.has(handle))
    : null;

  if (handles && handles.length > 0) {
    if (canUse(resolvedPreferred) && handles.includes(resolvedPreferred)) {
      return resolvedPreferred;
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
  serverUrl?: string;
  client?: ModelListClient;
}): Promise<string | undefined> {
  const {
    preferredModel,
    fallbackModel,
    availableHandles,
    disallowedHandles,
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
    });
  }

  if (!isSelfHosted) {
    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted: false,
      disallowedHandles,
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
    });
  } catch {
    return selectDefaultAgentModel({
      preferredModel,
      fallbackModel,
      isSelfHosted: true,
      disallowedHandles,
    });
  }
}
