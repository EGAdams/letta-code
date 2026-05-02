export function parseCsvListFlag(
  value: string | undefined,
): string[] | undefined {
  if (value === undefined) {
    return undefined;
  }

  const trimmed = value.trim();
  if (!trimmed || trimmed.toLowerCase() === "none") {
    return [];
  }

  return trimmed
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function normalizeConversationShorthandFlags(options: {
  specifiedConversationId: string | null | undefined;
  specifiedAgentId: string | null | undefined;
}) {
  let { specifiedConversationId, specifiedAgentId } = options;

  // Some callers pass a serialized one-item list (e.g. "['conv-...']").
  // Accept that shape and unwrap it to the raw conversation id.
  specifiedConversationId = normalizeSerializedConversationId(
    specifiedConversationId,
  );

  if (specifiedConversationId?.startsWith("agent-")) {
    if (specifiedAgentId && specifiedAgentId !== specifiedConversationId) {
      throw new Error(
        `Conflicting agent IDs: --agent ${specifiedAgentId} vs --conv ${specifiedConversationId}`,
      );
    }
    specifiedAgentId = specifiedConversationId;
    specifiedConversationId = "default";
  }

  return { specifiedConversationId, specifiedAgentId };
}

function normalizeSerializedConversationId(
  value: string | null | undefined,
): string | null | undefined {
  if (!value) {
    return value;
  }

  const unwrapOneLevel = (raw: string): string => {
    const trimmed = raw.trim();

    // JSON form: ["conv-..."]
    try {
      const parsed = JSON.parse(trimmed);
      if (
        Array.isArray(parsed) &&
        parsed.length === 1 &&
        typeof parsed[0] === "string"
      ) {
        return parsed[0];
      }
      // Also support double-serialized values like "\"['conv-...']\"".
      if (typeof parsed === "string") {
        return parsed;
      }
    } catch {
      // Not valid JSON; try Python-style single-quoted list next.
    }

    // Python-ish serialized form: ['conv-...']
    const singleQuotedListMatch = /^\[\s*'([^']+)'\s*\]$/.exec(trimmed);
    if (singleQuotedListMatch?.[1]) {
      return singleQuotedListMatch[1];
    }

    return raw;
  };

  let normalized = value;
  for (let i = 0; i < 3; i += 1) {
    const next = unwrapOneLevel(normalized);
    if (next === normalized) {
      break;
    }
    normalized = next;
  }

  return normalized;
}

export function resolveImportFlagAlias(options: {
  importFlagValue: string | undefined;
  fromAfFlagValue: string | undefined;
}): string | undefined {
  return options.importFlagValue ?? options.fromAfFlagValue;
}

export function parsePositiveIntFlag(options: {
  rawValue: string | undefined;
  flagName: string;
}): number | undefined {
  const { rawValue, flagName } = options;
  if (rawValue === undefined) {
    return undefined;
  }
  const parsed = Number.parseInt(rawValue, 10);
  if (Number.isNaN(parsed) || parsed <= 0) {
    throw new Error(
      `--${flagName} must be a positive integer, got: ${rawValue}`,
    );
  }
  return parsed;
}

export function parseJsonArrayFlag(
  rawValue: string,
  flagName: string,
): unknown[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawValue);
  } catch (error) {
    throw new Error(
      `Invalid --${flagName} JSON: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${flagName} must be a JSON array`);
  }
  return parsed;
}
