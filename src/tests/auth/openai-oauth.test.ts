import { describe, expect, test } from "bun:test";
import {
  extractAccountIdFromToken,
  OPENAI_OAUTH_CONFIG,
  startOpenAIOAuth,
} from "../../auth/openai-oauth";

function base64UrlJson(value: unknown): string {
  return Buffer.from(JSON.stringify(value), "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function makeJwt(payload: unknown): string {
  return [
    base64UrlJson({ alg: "none", typ: "JWT" }),
    base64UrlJson(payload),
    "signature",
  ].join(".");
}

describe("OpenAI OAuth helpers", () => {
  test("startOpenAIOAuth builds Codex-compatible authorization URL", async () => {
    const result = await startOpenAIOAuth(17891);
    const url = new URL(result.authorizationUrl);

    expect(url.origin + url.pathname).toBe(
      OPENAI_OAUTH_CONFIG.authorizationUrl,
    );
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("client_id")).toBe(
      OPENAI_OAUTH_CONFIG.clientId,
    );
    expect(url.searchParams.get("redirect_uri")).toBe(
      `http://localhost:17891${OPENAI_OAUTH_CONFIG.callbackPath}`,
    );
    expect(url.searchParams.get("scope")).toBe(OPENAI_OAUTH_CONFIG.scope);
    expect(url.searchParams.get("state")).toBe(result.state);
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(url.searchParams.get("id_token_add_organizations")).toBe("true");
    expect(url.searchParams.get("codex_cli_simplified_flow")).toBe("true");
    expect(url.searchParams.get("originator")).toBe("codex_cli_rs");
    expect(result.redirectUri).toBe(
      `http://localhost:17891${OPENAI_OAUTH_CONFIG.callbackPath}`,
    );
    expect(result.codeVerifier).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  test("extractAccountIdFromToken reads ChatGPT account id claim", () => {
    const token = makeJwt({
      "https://api.openai.com/auth": {
        chatgpt_account_id: "acct_abc123",
      },
    });

    expect(extractAccountIdFromToken(token)).toBe("acct_abc123");
  });

  test("extractAccountIdFromToken rejects malformed or missing claims", () => {
    expect(() => extractAccountIdFromToken("not-a-jwt")).toThrow(
      "Invalid JWT format",
    );
    expect(() => extractAccountIdFromToken(makeJwt({ sub: "user-1" }))).toThrow(
      "chatgpt_account_id not found",
    );
  });
});
