# Agent Handoff Patterns

## Strong kickoff message pattern

Use a message like this when one agent is taking over:

```text
You are taking over part of this project.

Current state:
- ...
- ...

Critical files:
- ...
- ...

Important rules:
- ...

Please reply with:
1. a compact summary of the current state
2. the next 3 tasks
3. whether you are ready to continue
```

## When memory may not surface reliably

If the target agent must act now, include the key facts inline even if you believe they are already in memory.

## Better than “are you up to speed?”

Avoid only asking:

```text
Are you up to speed?
```

Instead ask for specific recall:

```text
Summarize the current project state, list the key file paths, and give the next 3 planning tasks.
```

## Conversation-ID request pattern

If the user will continue directly with the other agent, ask for a reply that includes a conversation ID usable from the current server context.