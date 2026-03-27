---
name: fixing-model-selector-self-hosted
description: Diagnoses and fixes issues where the /model selector doesn't show expected models on self-hosted Letta servers. Covers: BYOK providers (chatgpt-plus-pro, lc-gemini, etc.) not appearing, agent stuck on wrong provider, ModelSelector tab logic for self-hosted, and how to inject models.json handles for providers the server doesn't list.
---

# Fixing /model Selector on Self-Hosted Letta

## Architecture

The `/model` selector (`src/cli/components/ModelSelector.tsx`) shows different tabs depending on context:

- **Letta Cloud** (`api.letta.com`): `supported`, `all`, `byok`, `byok-all`
- **Self-hosted**: `server-recommended`, `server-all` (+ `byok`, `byok-all` after this fix)

`server-recommended` and `server-all` only show models from the server's `/v1/models` endpoint. Self-hosted Letta servers (especially older versions like 0.16.x) do **not** list BYOK provider models (e.g. `chatgpt-plus-pro/*`) in `/v1/models` — even if the provider is registered.

## Diagnosing "model not in /model selector"

### 1. Check what the server lists
```bash
curl -sL http://<LETTA_BASE_URL>/v1/models/ | python3 -c "
import sys,json
models=json.load(sys.stdin)
providers=set(m.get('provider_name','') for m in models)
print('Providers:', providers)
"
```

### 2. Check what providers are registered
```bash
curl -sL http://<LETTA_BASE_URL>/v1/providers/ | python3 -m json.tool
```
Look for `chatgpt-plus-pro` (type: `chatgpt_oauth`) or `lc-gemini` etc.

### 3. Check what model the agent is using
```bash
curl -sL "http://<LETTA_BASE_URL>/v1/agents/<AGENT_ID>" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('model'), d.get('llm_config',{}).get('provider_name'))"
```

If the agent is on `provider_name: "openai"` with `DUMMY_API_KEY`, it needs to be switched to a BYOK provider model.

## The Fix — ModelSelector.tsx

The issue is in `src/cli/components/ModelSelector.tsx`:

### Problem 1: No byok tabs for self-hosted

```ts
// BEFORE — self-hosted never saw byok tabs
export function getModelCategories(
  _billingTier?: string,
  isSelfHosted?: boolean,
): ModelCategory[] {
  if (isSelfHosted) {
    return ["server-recommended", "server-all"];
  }
  return ["supported", "all", "byok", "byok-all"];
}

// AFTER — byok tabs included for self-hosted
export function getModelCategories(
  _billingTier?: string,
  isSelfHosted?: boolean,
): ModelCategory[] {
  if (isSelfHosted) {
    return ["server-recommended", "server-all", "byok", "byok-all"];
  }
  return ["supported", "all", "byok", "byok-all"];
}
```

### Problem 2: byokModels only uses server-reported handles

The `byokModels` and `byokAllModels` useMemos relied on `allApiHandles.filter(isByokHandle)`.
On self-hosted, the server doesn't list `chatgpt-plus-pro/*` handles, so that filter returns empty.

**Fix**: Add `extraByokHandles` that injects handles from `models.json` for registered BYOK providers
the server doesn't list. Place this useMemo after the `byokProviderAliases` state and before `pickPreferredStaticModel`:

```ts
// Handles from models.json for registered BYOK providers that the server doesn't list
// (e.g., chatgpt-plus-pro on self-hosted Letta — provider is registered but /v1/models
// doesn't include chatgpt-plus-pro/* handles)
const extraByokHandles = useMemo(() => {
  const serverHandleSet = new Set(allApiHandles);
  const extra: string[] = [];
  for (const providerName of Object.keys(byokProviderAliases)) {
    const prefix = `${providerName}/`;
    for (const m of typedModels) {
      if (m.handle.startsWith(prefix) && !serverHandleSet.has(m.handle)) {
        extra.push(m.handle);
      }
    }
  }
  return extra;
}, [typedModels, allApiHandles, byokProviderAliases]);
```

Then update both `byokModels` and `byokAllModels` to spread in `extraByokHandles`:

```ts
// In byokModels:
const byokHandles = [...allApiHandles.filter(isByokHandle), ...extraByokHandles];

// In byokAllModels:
const byokHandles = [...allApiHandles.filter(isByokHandle), ...extraByokHandles];
```

Add `extraByokHandles` to both dependency arrays.

### Update the test

`src/tests/cli/model-selector-categories.test.ts` — update the self-hosted test:

```ts
test("includes byok tabs for self-hosted (chatgpt-plus-pro may be registered)", () => {
  expect(getModelCategories("free", true)).toEqual([
    "server-recommended",
    "server-all",
    "byok",
    "byok-all",
  ]);
});
```

## After fixing — how to switch the agent

1. Run `bun run build` (or `letta-dev` uses source directly)
2. Open letta and run `/model`
3. Tab to **BYOK** — `chatgpt-plus-pro/gpt-*` models will now appear
4. Select the desired model

## Related skills

- `connecting-llm-oauth` — diagnoses broken OAuth tokens, stale oauthState, provider registration
