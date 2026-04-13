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

### 4. Verify the agent has a full handle (not just bare model name)
```bash
curl -sL "http://<LETTA_BASE_URL>/v1/agents/<AGENT_ID>" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); llm=d.get('llm_config',{}); print('model=', llm.get('model')); print('handle=', llm.get('handle')); print('provider=', llm.get('provider_name')); print('endpoint_type=', llm.get('model_endpoint_type'));"
```

If an agent has a bare model like `gpt-5-mini` with `chatgpt_oauth`, it may fail with BYOK credential errors. Prefer a full provider handle like `chatgpt-plus-pro/gpt-5.3-codex`.

### 5. Quick API fix for a stuck agent

```bash
curl -sS -X PATCH "http://<LETTA_BASE_URL>/v1/agents/<AGENT_ID>" \
  -H 'Content-Type: application/json' \
  -d '{"model":"chatgpt-plus-pro/gpt-5.3-codex"}'
```

This can immediately resolve `ChatGPT OAuth requires BYOK provider credentials` when the provider exists but the agent model mapping is incomplete.

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

## Fixing "NOT_FOUND: Handle ... not found, must be one of []"

This error appears when `/model` tries to switch an agent to a `chatgpt-plus-pro/*` model
but the OAuth provider isn't registered on the Letta server.

**Error pattern:**
```
Failed to switch model to GPT-5.4 Fast (ChatGPT): NOT_FOUND: Handle chatgpt-plus-pro/gpt-5.4-fast not found, must be one of []
```

The empty `[]` means the server has **no registered handles for that provider** — the provider
itself hasn't been connected.

### Diagnosis

```bash
# Check if the chatgpt-plus-pro provider exists on the server
curl -s http://<LETTA_BASE_URL>/v1/providers | python3 -c "
import sys,json
providers=json.load(sys.stdin)
for p in providers:
    print(p.get('provider_name'), p.get('provider_type'))
"
```

If `chatgpt-plus-pro` is **not** in the output → provider not registered → run `/connect chatgpt`.

If `chatgpt-plus-pro` **is** in the output but model switch still fails:
```bash
# Check what models the server lists for this provider
curl -sL http://<LETTA_BASE_URL>/v1/models/ | python3 -c "
import sys,json
models=json.load(sys.stdin)
chatgpt=[m for m in models if 'chatgpt' in m.get('provider_name','')]
for m in chatgpt: print(m.get('handle'))
"
```

If that list is empty, use the quick PATCH fix (below).

### Fix

**Step 1 — Register the provider**

In letta-code, run:
```
/connect chatgpt
```
This registers the `chatgpt-plus-pro` OAuth provider on the Letta server. If `~/.codex/auth.json`
exists with valid tokens it completes without a browser flow.

**Step 2 — Try /model again**

After `/connect chatgpt` completes, open `/model`, tab to **BYOK**, and select the ChatGPT model.

**Step 3 — If still failing: direct PATCH**

```bash
curl -sS -X PATCH "http://<LETTA_BASE_URL>/v1/agents/<AGENT_ID>" \
  -H 'Content-Type: application/json' \
  -d '{"model":"chatgpt-plus-pro/gpt-5.4-fast"}'
```

This bypasses the model-selector validation and sets the model directly on the agent.

## Related skills

- `connecting-llm-oauth` — diagnoses broken OAuth tokens, stale oauthState, provider registration
