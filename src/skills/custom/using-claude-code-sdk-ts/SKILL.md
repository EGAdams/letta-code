---
name: using-claude-code-sdk-ts
description: "Use this skill when you need to integrate, script, or explain the TypeScript Claude Code SDK (fluent API, classic async generator API, permissions, streaming, and logging)."
---

# Using Claude Code SDK (TypeScript)

## Overview

Use this skill to implement or explain integrations with `@instantlyeasy/claude-code-sdk-ts`, including fluent API usage, classic async generator usage, permissions, streaming, and logging.

## Quick start (most common)

```ts
import { claude } from '@instantlyeasy/claude-code-sdk-ts';

const response = await claude()
  .query('Say "Hello World!"')
  .asText();

console.log(response);
```

## Core workflows

### 1) Fluent API (recommended)

```ts
const result = await claude()
  .withModel('sonnet')
  .allowTools('Read', 'Write')
  .skipPermissions()
  .inDirectory('/path/to/project')
  .query('Refactor this code')
  .asText();
```

### 2) Classic async generator API

```ts
import { query } from '@instantlyeasy/claude-code-sdk-ts';

for await (const message of query('Create a hello.txt file')) {
  console.log(message);
}
```

## Common tasks

### Parse JSON responses

```ts
const data = await claude()
  .query('Return a JSON array of files')
  .asJSON<string[]>();
```

### Manage tools and permissions

```ts
await claude()
  .allowTools('Read', 'Grep')
  .skipPermissions()
  .query('Analyze this repo')
  .asText();
```

### Sessions

```ts
const session = claude().withModel('sonnet').skipPermissions();
const response1 = await session.query('Pick a number').asText();
const sessionId = await session.query('').getSessionId();
const response2 = await session.withSessionId(sessionId)
  .query('What number did you pick?')
  .asText();
```

### Streaming and cancellation

```ts
const controller = new AbortController();
setTimeout(() => controller.abort(), 5000);

const parser = claude().withSignal(controller.signal).query('Long task');
await parser.stream(async (message) => {
  if (message.type === 'assistant') {
    console.log(message.content[0].text); // full text block
  }
});
```

### Logging

```ts
import { ConsoleLogger, LogLevel } from '@instantlyeasy/claude-code-sdk-ts';

const logger = new ConsoleLogger(LogLevel.DEBUG);
await claude().withLogger(logger).query('Debug this').asText();
```

## References

Load these when needed:
- `references/README.md` — consolidated API summary with examples
- `references/PROJECT_LAYOUT.md` — source tree & key files

## Notes

- Auth is delegated to the Claude CLI (`claude login`).
- Streaming delivers full message blocks, not per-token deltas.
