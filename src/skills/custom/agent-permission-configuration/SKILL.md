---
name: agent-permission-configuration
description: "Configure agent permission modes to control tool approval behavior. Use when an agent waits for approval on every tool call, or to enable autonomous tool execution."
---

# Agent Permission Configuration

## Problem

An agent is stuck waiting for user approval on every tool call (bash commands, file edits, etc.), blocking autonomous execution.

## Root Cause

The agent's entry in `~/.letta/settings.json` is missing a `permissionMode` setting, defaulting to `default` (all tools require approval).

## Solution

1. Locate your agent in `~/.letta/settings.json`:

```bash
grep -A 5 "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa" ~/.letta/settings.json
```

2. Add `"permissionMode"` to the agent's configuration object:

```json
{
  "agentId": "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
  "baseUrl": "100.80.49.10:8283",
  "memfs": true,
  "memfsRemote": "http://10.0.0.143:8283",
  "permissionMode": "acceptEdits"
}
```

3. Restart the letta-code CLI for changes to take effect.

## Permission Mode Reference

| Mode | Behavior | Use Case |
|------|----------|----------|
| `default` | Every tool requires user approval | Development, testing, high-scrutiny scenarios |
| `acceptEdits` | Auto-approve file ops (Edit, Write, Patch) and bash commands; interactive tools (AskUserQuestion, Planning) still prompt | **Recommended for autonomous agents like Scissari** |
| `plan` | Auto-approve everything except planning tools (EnterPlanMode, ExitPlanMode) | Agents that plan but shouldn't auto-approve plans |
| `bypassPermissions` | Auto-approve all tools without prompting | Sandboxed/safe environments only |

## Architecture

- **Settings location:** `~/.letta/settings.json` on the machine running letta-code CLI
- **Scope:** Client-side setting controlling CLI approval behavior, not agent server config
- **Override:** Use `.letta/settings.local.json` in a project directory to override global settings for that project only

## Example: Scissari on Windows 11

Scissari runs on a Letta Server (Docker on Windows 10), but letta-code CLI runs on Windows 11. The permission mode is set in Windows 11's `~/.letta/settings.json`:

```json
"agents": [
  {
    "agentId": "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
    "baseUrl": "100.80.49.10:8283",
    "permissionMode": "acceptEdits"  ← Windows 11 setting controls approval behavior
  }
]
```

When Scissari requests a bash tool, the CLI checks this setting and auto-approves without prompting.

## Verification

Run the agent with the new mode and verify it auto-executes commands:

```bash
letta -a agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
# Type a prompt that triggers bash commands
# Commands should execute without "Approve?" prompts
```

## Related

- Memory: [project_agent_permission_modes](../../../../../../.claude/projects/-home-adamsl-letta-code/memory/project_agent_permission_modes.md)
- Skill: [debugging-executor-run](../debugging-executor-run/SKILL.md) — if agent tool calls fail, not just get stuck on approval
- Tool registration: [project_letta_tool_registration](../../../../../../.claude/projects/-home-adamsl-letta-code/memory/project_letta_tool_registration.md) — if tools show "Tool not found" instead of executing
