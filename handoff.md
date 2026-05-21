# Handoff: Scissari / cross-machine Letta setup / ROL Finances transfer

---

## Skills used in this shift

- `letta-admin`
  - used for Letta server health, Windows/WSL `8283` bridge repair, agent tool attachment checks, Scissari↔Hailey message verification, and Telegram bot recovery

## ⚠️ ACTIVE BLOCKER — April 14, 2026 end-of-shift (pick up here first)

**The remaining issue is now client-side Letta Code fallback behavior, not the server/tool path.**

Current verified state:
- `http://100.80.49.10:8283/v1/health/` returns Letta `0.16.7`
- `Scissari`, `Hailey`, and `Quinn` all have `send_message_to_agent_async`
- `Scissari` also has `send_message_to_agent_and_wait_for_reply`
- real async message delivery between `Scissari` and `Hailey` was verified both directions from the API by checking recent messages
- Telegram to `@scissaribot` was repaired and confirmed working end-to-end

The still-open user-facing failure looks like this:
```text
Quota limit reached; temporarily switching to Auto and continuing...
NOT_FOUND: Handle letta/auto not found, must be one of []
```

This is a Letta Code client bug on this self-hosted setup:
- the CLI falls back to hardcoded `letta/auto`
- this server does not expose a usable `letta/auto` handle for that path
- the message-send tool path is already working underneath

### Exact code locations for the next shift

- `/home/adamsl/letta-code/src/cli/App.tsx`
  - `const TEMP_QUOTA_OVERRIDE_MODEL = "letta/auto";`
  - quota-limit branch calls `setTempModelOverride(TEMP_QUOTA_OVERRIDE_MODEL)`
- `/home/adamsl/letta-code/src/constants.ts`
  - `DEFAULT_SUMMARIZATION_MODEL = "letta/auto"`
- `/home/adamsl/letta-code/src/agent/defaults.ts`
  - already has self-hosted-safe selection logic that prefers the first available non-auto handle

### Recommended next step

Patch Letta Code so quota fallback chooses an actually available model handle on self-hosted servers instead of hardcoding `letta/auto`, then retest Scissari from a fresh CLI/ADE session.

### Important operational note

If the next person sees the `Quota limit reached ... letta/auto not found` sequence, do **not** start by reattaching tools again. First verify delivery server-side via the recipient agent's recent messages.

## Historical blocker from earlier in the day

This was the earlier top-of-file blocker before the `8283`/tooling work. Keep it for reference only unless a fresh `401` reproduces again.

## ⚠️ Earlier blocker — April 14, 2026

**ChatGPT OAuth authentication is broken.** Scissari, Hailey, and Quinn all fail with:
```
HTTP 401: UNAUTHENTICATED: Failed to obtain valid ChatGPT OAuth credentials
```

### What was done
- Fresh tokens copied from Rosemary46 (AOL Plus account `rbarnersrol@aol.com`, account_id `a0eafe76`)
- `_update_stored_credentials()` run via `docker exec` to write properly-encoded credentials
- Server restarted — still 401

### Root cause (hypothesis, not confirmed)
`CryptoUtils.decrypt(plain_json)` raises `ValueError: No encryption key configured` when `LETTA_ENCRYPTION_KEY` is not set. Plain JSON written to `api_key_enc` (even via `_update_stored_credentials`) can't be read back properly after restart.

### What to try next

**Step 1 — Check server logs during a live 401 for actual traceback:**
```bash
docker logs letta-server -f --since 0s &
curl -s -m 30 -X POST \
  -H "Authorization: Bearer 6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8" \
  -H "Content-Type: application/json" \
  "http://100.80.49.10:8283/v1/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/messages" \
  -d '{"messages":[{"role":"user","content":"Say hello."}]}'
```

**Step 2 — Test the Secret roundtrip directly:**
```bash
docker exec letta-server python3 -c "
import asyncio
async def test():
    from letta.schemas.secret import Secret
    s = await Secret.from_plaintext_async('{\"test\": 1}')
    print('encrypted_value:', repr(s.encrypted_value[:60]))
    pt = await s.get_plaintext_async()
    print('roundtrip:', repr(pt))
asyncio.run(test())
" 2>&1
```

**Step 3 — Check if LETTA_ENCRYPTION_KEY was ever set:**
```bash
cat ~/.letta/.env | grep -i encrypt
docker exec letta-server env | grep -i encrypt
```
If it was set before, add it to `docker-compose.prod.yml` env block and restart.

**Step 4 — Try the `connecting-llm-oauth` skill** — that is the installed OAuth repair skill in this workspace.

### Key IDs
| Item | Value |
|------|-------|
| Scissari | `agent-5955b0c2-7922-4ffe-9e43-b116053b80fa` |
| Hailey | `agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03` |
| Quinn | `agent-fcbd78e5-abcd-459e-852e-921d4946223e` |
| Provider | `provider-8903011f-f1fd-4312-b5e2-b3ad90ae2031` |
| Correct account | `rbarnersrol@aol.com` — Plus — `a0eafe76-9d03-4f32-a4c4-f719aab9bfbd` |
| Wrong account | `rbarnesrol@gmail.com` — Free — `deed1d33-ba9d-4d01-9479-885b400b4d11` |
| Letta server | `http://100.80.49.10:8283` (Tailscale) — `10.0.0.143` portproxy is DEAD |
| API key | `6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8` |
| Auth.json | `/home/adamsl/.codex/auth.json` — fresh AOL Plus tokens, ready to re-push |

---

## High-level goal

We are transferring responsibility for the ROL Finances planning effort to **Scissari** and making sure she can be accessed and used reliably from multiple machines.

There were two parallel tracks:

1. **Project handoff to Scissari**
   - move the ROL Finances plans, workflow, and current state into Scissari's memory
   - make sure Scissari can answer questions about the finance workflow, next steps, and agent-construction plan

2. **Cross-machine operational setup**
   - make Scissari usable from other machines
   - support custom Letta startup wrappers that can create/open conversations and expose `conversation_id`
   - make memfs sync across machines where possible

---

## Scissari identity and conversation info

- Agent ID:

```text
agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

- Clean handoff confirmation conversation:

```text
conv-5e450cce-9f6b-47d1-989e-efbbbef629e8
```

- Example test conversation created later via wrapper script:

```text
conv-48318f9e-ee28-4308-84b5-0b44a3bb1a0b
```

---

## What was transferred into Scissari's memory

Scissari received ROL Finances handoff content in both core blocks and memfs files.

### Important project facts saved for Scissari

- Active pipeline entrypoint:

```text
/home/adamsl/rol_finances/e_two_e_processing/process.py
```

- Duplicate root copy also exists:

```text
/home/adamsl/rol_finances/process.py
```

- The `vendor_key` / `id_light` ordering issue has already been fixed in both process files.

- The critical rule now is:
  - build `id_light` only after final vendor resolution / user override
  - then use that final `id_light` for:
    - `raw_id_lights`
    - duplicate detection
    - categorizer payloads
    - receipt linking
    - final inserts

- Regression test added:

```text
/home/adamsl/rol_finances/tests/test_process_vendor_ordering.py
```

- Local full test execution was blocked by missing `pytest` and `pydantic`; syntax was checked with `py_compile`

- Immediate likely next work for Scissari:
  - draft agent documents
  - draft JSON handoff contracts / envelopes
  - refine the agent workflow for the finance/reporting system

### Full planning docs that were part of the handoff

- `/home/adamsl/rol_finances/plans/team_construction_plan.md`
- `/home/adamsl/rol_finances/plans/document_processing_steps.md`
- `/home/adamsl/.letta/plans/shiny-witty-brook.md`
- `/home/adamsl/rol_finances/e_two_e_processing/process_docs_diagrams/documentation/plan_with_sequence.md`

### Supporting docs reviewed during the planning pass

- `tools/categorization_process.md`
- `tools/categorizer/categorizer_main_sequence.md`
- `tools/categorizer/resolve_vendor_key/resolve_vendor_key_documentation.md`
- `external_agents/AGENT_REGISTRY.md`
- `external_agents/AGENT_REGISTRY.json`

### Confirmed artifact

- Gemini-parsed mom's-ledger output exists at:

```text
readable_documents/ledger_documents/moms_ledger_page_2/moms_ledger_page_2_router_parse.json
```

---

## Scissari memfs state

### Local memory path

On the main machine, Scissari memory lives at:

```text
~/.letta/agents/agent-5955b0c2-7922-4ffe-9e43-b116053b80fa/memory
```

### Intended shared memfs remote

We set up a shared SSH git remote for Scissari memory:

```text
ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/scissari-memory.git
```

### Historical caveat

During this shift, cross-machine memfs on mom's Ubuntu machine was temporarily blocked.

Problem that was found:
- mom's Ubuntu machine (`rosemary46-24`) still had Scissari memfs pointed at an old HTTP remote
- it also showed local untracked memfs content
- when attempting to switch that machine to the shared SSH remote, SSH auth from **that remote machine** to `desktop-2obsqmc-24` failed

The blocker command was:

```bash
ssh adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net echo ok
```

from `rosemary46-24`, which failed with publickey auth issues.

That blocker was later resolved by appending `rosemary46-24`'s `~/.ssh/id_ed25519.pub` key to `desktop-2obsqmc-24`'s `~/.ssh/authorized_keys`.

After that, Scissari memfs on `rosemary46-24` was migrated cleanly to the shared SSH remote and verified clean.

---

## Machine / Tailscale notes

### Relevant hosts

- `desktop-2obsqmc-24`
  - Linux / WSL side
  - shared memfs remote host for Scissari

- `desktop-2obsqmc-11`
  - Windows side

- `rosemary46-24`
  - mom's Ubuntu / WSL side
  - this is where Linux paths like `/home/adamsl/...` live

- `rosemary46-11`
  - Windows side on mom's machine

### Important operational rule

When files live under `/home/adamsl/...`, target the **Ubuntu/WSL** host, not the Windows host.

Also: prefer `scp` over asking the user to copy/paste files manually when remote access is available.

This preference was explicitly clarified by the user near the end of the shift.

---

## Remote machine setup findings (mom's Ubuntu / rosemary46-24)

We were able to SSH into:

```text
adamsl@100.72.34.38
```

and confirm:
- SSH server was running
- Tailscale was connected

### PATH issue found on remote non-interactive shell

When trying to run Letta tools remotely, `node` and `bun` were missing from PATH in non-interactive SSH sessions.

Observed remote PATH initially lacked:
- `~/.bun/bin`
- `~/.nvm/versions/node/<version>/bin`

Workaround used in SSH commands:

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | tail -n 1)/bin:$PATH"
```

After doing that, remote checks succeeded for:
- `which node`
- `which bun`
- `node --version`
- `bun --version`

This is now part of the reusable skill docs.

---

## Wrapper script work

We inspected this script on `rosemary46-24`:

```text
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh
```

### Original issue

The script was fine for launching Letta in a target directory, but it did **not** expose a `conversation_id` during startup.

### Desired behavior

Support modes that can:
- create a new conversation and print only the `conversation_id`
- create a new conversation, print/log the `conversation_id`, then open it interactively
- save the latest `conversation_id` to files

### Tested result

The user replaced/updated the remote script enough that this worked:

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-id-only --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

and it returned:

```text
conv-5c92f457-bb51-46b0-9338-01bbf498c4f0
```

Then this also worked:

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-with-id --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

and it logged:

```text
[run-local-in-dir] conversation_id: conv-48318f9e-ee28-4308-84b5-0b44a3bb1a0b
```

then dropped into the interactive session successfully.

### Additional file-saving version prepared

I created a script variant that saves the latest conversation ID to:
- `${TARGET_DIR}/.last_letta_conversation_id`
- `~/.last_letta_conversation_id`

That file was copied to mom's Ubuntu machine here:

```text
/home/adamsl/run_local_with_conv_save.sh
```

It was **not yet installed as the main production wrapper** at the end of the shift. It was only copied there.

---

## Files created during this shift

### Local docs / helper files

- `/home/adamsl/letta-code/useful_patterns.md`
- `/home/adamsl/letta-code/handoff.md` (this file)

### Remote copied files on mom's Ubuntu machine

- `/home/adamsl/useful_patterns.md`
- `/home/adamsl/run_local_with_conv_save.sh`

---

## Skills created this shift

Two new reusable skills were created to preserve the workflow we discovered.

### 1. `operating-letta-across-machines`

Source:

```text
/home/adamsl/letta-code/src/skills/custom/operating-letta-across-machines
```

Installed project skill:

```text
/home/adamsl/letta-code/.skills/operating-letta-across-machines
```

Packaged skill:

```text
/home/adamsl/operating-letta-across-machines.skill
```

Purpose:
- Tailscale / SSH / SCP across machines
- choosing WSL/Linux vs Windows host correctly
- remote PATH / node / bun debugging
- remote memfs verification
- Scissari-specific remote memfs notes

### 2. `managing-letta-conversation-launchers`

Source:

```text
/home/adamsl/letta-code/src/skills/custom/managing-letta-conversation-launchers
```

Installed project skill:

```text
/home/adamsl/letta-code/.skills/managing-letta-conversation-launchers
```

Packaged skill:

```text
/home/adamsl/managing-letta-conversation-launchers.skill
```

Purpose:
- wrapper scripts like `run-local-in-dir.sh`
- creating/opening/reopening Letta conversations from scripts
- printing and saving `conversation_id`
- useful wrapper patterns for Scissari

These skills are expected to be refined over time.

---

## Important user preferences clarified during shift

1. **One step at a time**
   - the user explicitly requested sequential instructions and to wait after each step when guiding them interactively

2. **Prefer `scp` over manual copy/paste**
   - if a file needs to go to another machine and SSH/SCP is available, prefer `scp`

---

## What still remains unfinished

### 1. Decide whether to install the conversation-saving wrapper as the main script

The improved conversation-saving variant exists on mom's machine as:

```text
/home/adamsl/run_local_with_conv_save.sh
```

but the active script in the upstream repo path may still be a different version.

Need to decide whether to:
- replace `/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh`
- or keep the helper as a separate file

### 2. Resume the actual Scissari takeover work

The broader objective is still to make Scissari take over:
- the ROL Finances planning work
- the finance report / workflow planning
- the agent-construction responsibility

Infrastructure work dominated this shift, but the bigger goal is still the Scissari project handoff.

---

## Best next actions for next shift

1. Verify Scissari memory is still synced cleanly across machines
2. Decide whether to install the conversation-saving wrapper as the canonical `run-local-in-dir.sh`
3. Return to the actual finance/agent-planning work with Scissari

---

## Quick reference commands

### Reopen Scissari conversation

```bash
letta --conversation conv-5e450cce-9f6b-47d1-989e-efbbbef629e8
```

### Wrapper patterns

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-id-only --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-with-id --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

### Remote env PATH workaround on mom's Ubuntu machine

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" | tail -n 1)/bin:$PATH"
```

### Scissari memfs shared remote target

```text
ssh://adamsl@desktop-2obsqmc-24.tailb8fc54.ts.net/home/adamsl/memfs/scissari-memory.git
```
