---
name: reliable-agent-messaging
description: Sends more reliable messages between Letta agents, especially for handoffs, takeovers, and project coordination. Use when one agent needs another agent to understand project state, confirm what it knows, continue work, or reply with a useful conversation ID.
---

# Reliable Agent Messaging

## Overview

Use this skill when one agent needs to hand work to another agent and wants the reply to be dependable, specific, and easy for the user to continue from.

## Core rules

1. Do **not** assume that because memory exists, the receiving agent will surface it correctly in the very next reply.
2. If the receiving agent must act immediately, include the critical context inline in the message.
3. Ask the receiving agent to summarize what it understands, not just say “yes”.
4. If the user will continue directly with the target agent, ask for a **conversation ID** in the reply.
5. Prefer compact bullet-point state transfer over vague prose.

## Good handoff pattern

Include these pieces explicitly:
- current project state
- critical file paths
- key fixes or invariants
- next 1-3 tasks
- what the target agent should be ready to do next

## Ask for verification

When accuracy matters, ask the receiving agent to answer in a structured way such as:
- summary of current state
- next 3 tasks
- whether it is ready to continue

This is more reliable than asking “do you understand?”

## If you need a usable follow-up thread

When the user will talk to the other agent next, ask the receiving agent to return or confirm a conversation ID that can be resumed from the current server context.

## References

Use these references as needed:
- `references/handoff-patterns.md`
- `references/scissari-example.md`
- `references/scissari-telegram-noreply.md` — Scissari's no-reply behavior over Telegram and how to fix it
