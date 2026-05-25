# Agent Session Context Checklist

## 1. Confirm identity and server

- same agent ID?
- same Letta server?
- same account/auth context?

## 2. Confirm memory exists

Check blocks, memfs files, or other stored context.

## 3. Ask for specific recall

Use a question that demands exact facts, for example:

```text
Summarize the current project state, mention the active pipeline file path, and list the next 3 tasks.
```

## 4. Compare responses

- if the agent fails with a vague prompt but succeeds with a specific prompt, this is likely a messaging-quality issue
- if it fails even on exact facts, this is likely a session/context problem

## 5. If needed, resend compact context inline

Do not keep guessing. Send a short state summary and ask the agent to restate it back.