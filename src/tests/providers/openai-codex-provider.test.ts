import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  CHATGPT_OAUTH_PROVIDER_TYPE,
  checkOpenAICodexEligibility,
  createOpenAICodexProvider,
  createOrUpdateOpenAICodexProvider,
  getOpenAICodexProvider,
  listProviders,
  removeOpenAICodexProvider,
  updateOpenAICodexProvider,
} from "../../providers/openai-codex-provider";
import { settingsManager } from "../../settings-manager";

type SettingsSnapshot = {
  baseUrl?: string;
  apiKey?: string;
};

const originalFetch = globalThis.fetch;
const originalGetSettingsWithSecureTokens =
  settingsManager.getSettingsWithSecureTokens;
const originalEnv: SettingsSnapshot = {
  baseUrl: process.env.LETTA_BASE_URL,
  apiKey: process.env.LETTA_API_KEY,
};

const mockSettingsWithSecureTokens = mock(() =>
  Promise.resolve({
    env: {
      LETTA_BASE_URL: "https://letta.test",
      LETTA_API_KEY: "letta-api-key",
    },
  }),
);

function restoreEnvironment(): void {
  if (originalEnv.baseUrl !== undefined) {
    process.env.LETTA_BASE_URL = originalEnv.baseUrl;
  } else {
    delete process.env.LETTA_BASE_URL;
  }

  if (originalEnv.apiKey !== undefined) {
    process.env.LETTA_API_KEY = originalEnv.apiKey;
  } else {
    delete process.env.LETTA_API_KEY;
  }
}

function installCommonMocks(): void {
  process.env.LETTA_BASE_URL = "";
  process.env.LETTA_API_KEY = "";
  (settingsManager as typeof settingsManager).getSettingsWithSecureTokens =
    mockSettingsWithSecureTokens as unknown as typeof settingsManager.getSettingsWithSecureTokens;
}

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("openai codex provider helpers", () => {
  beforeEach(() => {
    installCommonMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    (settingsManager as typeof settingsManager).getSettingsWithSecureTokens =
      originalGetSettingsWithSecureTokens;
    restoreEnvironment();
  });

  test("createOpenAICodexProvider posts chatgpt_oauth payload", async () => {
    const fetchMock = mock((_url: string | URL, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse({
          id: "provider-1",
          name: "chatgpt-plus-pro",
          provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await createOpenAICodexProvider({
      access_token: "access-token",
      id_token: "id-token",
      refresh_token: "refresh-token",
      account_id: "acct_123",
      expires_at: 1_700_000_000_000,
    });

    expect(result.id).toBe("provider-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://letta.test/v1/providers");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toMatchObject({
      Authorization: "Bearer letta-api-key",
      "Content-Type": "application/json",
      "X-Letta-Source": "letta-code",
    });
    expect(JSON.parse(String(options?.body))).toEqual({
      name: "chatgpt-plus-pro",
      provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
      api_key: JSON.stringify({
        access_token: "access-token",
        id_token: "id-token",
        refresh_token: "refresh-token",
        account_id: "acct_123",
        expires_at: 1_700_000_000_000,
      }),
    });
  });

  test("updateOpenAICodexProvider patches api_key payload", async () => {
    const fetchMock = mock((_url: string | URL, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse({
          id: "provider-1",
          name: "chatgpt-plus-pro",
          provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await updateOpenAICodexProvider("provider-1", {
      access_token: "access-token",
      id_token: "id-token",
      refresh_token: "refresh-token",
      account_id: "acct_123",
      expires_at: 1_700_000_000_000,
    });

    expect(result.id).toBe("provider-1");
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://letta.test/v1/providers/provider-1");
    expect(options?.method).toBe("PATCH");
    expect(JSON.parse(String(options?.body))).toEqual({
      api_key: JSON.stringify({
        access_token: "access-token",
        id_token: "id-token",
        refresh_token: "refresh-token",
        account_id: "acct_123",
        expires_at: 1_700_000_000_000,
      }),
    });
  });

  test("createOrUpdateOpenAICodexProvider creates when provider is missing", async () => {
    const fetchMock = mock((url: string | URL, options?: RequestInit) => {
      if (String(url).endsWith("/v1/providers") && options?.method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }

      return Promise.resolve(
        jsonResponse({
          id: "provider-created",
          name: "chatgpt-plus-pro",
          provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await createOrUpdateOpenAICodexProvider({
      access_token: "access-token",
      id_token: "id-token",
      refresh_token: "refresh-token",
      account_id: "acct_123",
      expires_at: 1_700_000_000_000,
    });

    expect(result.id).toBe("provider-created");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "https://letta.test/v1/providers",
    );
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("GET");
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
  });

  test("createOrUpdateOpenAICodexProvider updates when provider exists", async () => {
    const fetchMock = mock((url: string | URL, options?: RequestInit) => {
      if (String(url).endsWith("/v1/providers") && options?.method === "GET") {
        return Promise.resolve(
          jsonResponse([
            {
              id: "provider-1",
              name: "chatgpt-plus-pro",
              provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
            },
          ]),
        );
      }

      return Promise.resolve(
        jsonResponse({
          id: "provider-1",
          name: "chatgpt-plus-pro",
          provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await createOrUpdateOpenAICodexProvider({
      access_token: "access-token",
      id_token: "id-token",
      refresh_token: "refresh-token",
      account_id: "acct_123",
      expires_at: 1_700_000_000_000,
    });

    expect(result.id).toBe("provider-1");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://letta.test/v1/providers/provider-1",
    );
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("PATCH");
  });

  test("removeOpenAICodexProvider deletes only when provider exists", async () => {
    const fetchMock = mock((url: string | URL, options?: RequestInit) => {
      if (String(url).endsWith("/v1/providers") && options?.method === "GET") {
        return Promise.resolve(
          jsonResponse([
            {
              id: "provider-1",
              name: "chatgpt-plus-pro",
              provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
            },
          ]),
        );
      }

      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await removeOpenAICodexProvider();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://letta.test/v1/providers/provider-1",
    );
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("DELETE");

    fetchMock.mockClear();
    const emptyFetchMock = mock((url: string | URL, options?: RequestInit) => {
      if (String(url).endsWith("/v1/providers") && options?.method === "GET") {
        return Promise.resolve(jsonResponse([]));
      }

      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = emptyFetchMock as unknown as typeof fetch;

    await removeOpenAICodexProvider();

    expect(emptyFetchMock).toHaveBeenCalledTimes(1);
    expect(String(emptyFetchMock.mock.calls[0]?.[0])).toBe(
      "https://letta.test/v1/providers",
    );
    expect(emptyFetchMock.mock.calls[0]?.[1]?.method).toBe("GET");
  });

  test("getOpenAICodexProvider returns the matching provider from the list", async () => {
    const fetchMock = mock(() =>
      Promise.resolve(
        jsonResponse([
          {
            id: "provider-2",
            name: "other-provider",
            provider_type: "openai",
          },
          {
            id: "provider-1",
            name: "chatgpt-plus-pro",
            provider_type: CHATGPT_OAUTH_PROVIDER_TYPE,
          },
        ]),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const provider = await getOpenAICodexProvider();

    expect(provider?.id).toBe("provider-1");
    expect(provider?.name).toBe("chatgpt-plus-pro");
  });

  test("checkOpenAICodexEligibility reports pro and enterprise as eligible", async () => {
    const fetchMock = mock((url: string | URL) => {
      const billingTier = String(url).includes("pro") ? "pro" : "enterprise";
      return Promise.resolve(
        jsonResponse({
          total_balance: 0,
          monthly_credit_balance: 0,
          purchased_credit_balance: 0,
          billing_tier: billingTier,
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    for (const billingTier of ["pro", "enterprise"] as const) {
      fetchMock.mockImplementationOnce(() =>
        Promise.resolve(
          jsonResponse({
            total_balance: 0,
            monthly_credit_balance: 0,
            purchased_credit_balance: 0,
            billing_tier: billingTier,
          }),
        ),
      );

      const result = await checkOpenAICodexEligibility();
      expect(result).toEqual({
        eligible: true,
        billing_tier: billingTier,
      });
    }
  });

  test("checkOpenAICodexEligibility rejects non-eligible tiers with reason", async () => {
    const fetchMock = mock(() =>
      Promise.resolve(
        jsonResponse({
          total_balance: 0,
          monthly_credit_balance: 0,
          purchased_credit_balance: 0,
          billing_tier: "free",
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await checkOpenAICodexEligibility();

    expect(result).toEqual({
      eligible: false,
      billing_tier: "free",
      reason:
        "ChatGPT OAuth requires a Pro or Enterprise plan. Current plan: free",
    });
  });

  test("checkOpenAICodexEligibility falls back to unknown on fetch failure", async () => {
    const warnMock = mock(() => undefined);
    const originalWarn = console.warn;
    console.warn = warnMock as typeof console.warn;

    const fetchMock = mock(() => Promise.reject(new Error("network down")));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await checkOpenAICodexEligibility();

    expect(result).toEqual({
      eligible: true,
      billing_tier: "unknown",
    });
    expect(warnMock).toHaveBeenCalledTimes(1);

    console.warn = originalWarn;
  });

  test("listProviders returns an empty array on request error", async () => {
    const fetchMock = mock(() => Promise.reject(new Error("request failed")));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(listProviders()).resolves.toEqual([]);
  });
});
