---
name: managing-letta-conversation-launchers
description: Manages custom shell wrappers and startup scripts that launch Letta, create conversations, reopen conversations, print conversation IDs, or save the latest conversation ID to files. Use when the user launches Letta through scripts instead of plain `letta`, or needs scripted conversation-id capture.
---

# Managing Letta Conversation Launchers

## Overview

Use this skill when the user starts Letta through a wrapper script instead of running `letta` directly.

This skill is for scripts like `run-local-in-dir.sh` that:
- set the working directory
- set `LETTA_BASE_URL`
- preflight the network/server
- then launch Letta

## When to use this skill

- The user mentions a startup script, wrapper, launcher, or shell helper for Letta
- The user needs a `conversation_id` during startup
- The user wants a script to create a new conversation and print its ID
- The user wants a script to save the latest `conversation_id` to a file
- The user wants to reopen a known conversation from a script

## Core pattern

Separate these launcher modes clearly:

1. **Normal interactive mode**
   - Start Letta normally in the target directory

2. **New conversation, print ID only**
   - Start Letta in machine-readable mode
   - capture the `conversation_id`
   - print it
   - exit

3. **New conversation, then open it interactively**
   - Create a new conversation programmatically
   - capture the `conversation_id`
   - print/log it
   - reopen that exact conversation interactively

4. **Reopen a known conversation**
   - launch Letta with `--conversation <id>`

## Practical rule

If the user needs a `conversation_id`, plain interactive `letta` is not enough.
Use a machine-readable startup flow first, then open the conversation interactively if needed.

## Save the latest conversation ID

When a wrapper creates a new conversation, it is often useful to save the ID to:

- a file inside the target directory
- a file in the user's home directory

This makes later reuse easy from scripts and shell history.

## References

Read these when implementing or updating a launcher script:

- `references/run-local-in-dir-pattern.md`
- `references/useful-patterns.md`
