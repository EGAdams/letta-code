---
name: debugging-agent-session-context
description: Diagnoses why an agent says it lacks context even when memory, files, or prior handoff work should exist. Use when an agent seems confused, forgets project state, cannot recall handoff details, or gives replies inconsistent with known stored memory.
---

# Debugging Agent Session Context

## Overview

Use this skill when an agent behaves as though it lacks context even though memory or previous handoff work should exist.

The main job is to determine whether the problem is:
- messaging quality
- memory/session surfacing
- server/auth mismatch
- conversation mismatch

## Core diagnostic idea

Do not assume “the memory exists” means “the agent can or will use it in this reply.”

Test the current session directly.

## Checklist

1. Confirm the same agent ID is being used.
2. Confirm the same server / account context is being used.
3. Confirm the relevant memory files or blocks really exist.
4. Ask the target agent a question that requires a **specific stored fact**.
5. If it still fails, resend a compact handoff inline and compare the response.

## Strong test questions

Ask for facts that are hard to fake, such as:
- exact pipeline file path
- exact conversation ID
- specific invariant like the `vendor_key` / `id_light` rule
- next 3 tasks from the handoff

## Important lesson

An agent-to-agent message thread may not reflect the same working context as the one where memory was originally confirmed.

So when debugging, separate:
- **memory storage exists**
- **memory is visible in this session**
- **the current message asked the right thing**

## References

Read these when needed:
- `references/checklist.md`
- `references/failure-modes.md`
