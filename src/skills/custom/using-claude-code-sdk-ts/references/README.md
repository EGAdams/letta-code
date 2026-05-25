# Claude Code SDK (TypeScript) Reference

Source repo: `/home/adamsl/claude-code-sdk-ts`

## Table of Contents
- [Install & prerequisites](#install--prerequisites)
- [Quick start](#quick-start)
- [Core API surface](#core-api-surface)
- [Fluent API](#fluent-api)
- [Response parsing](#response-parsing)
- [Sessions](#sessions)
- [Tool permissions](#tool-permissions)
- [Streaming & cancellation](#streaming--cancellation)
- [Logging](#logging)
- [Event handlers](#event-handlers)
- [Auth & environment](#auth--environment)
- [Build & test](#build--test)

## Install & prerequisites

```bash
npm install @instantlyeasy/claude-code-sdk-ts
# or yarn add / pnpm add
```

Prereqs:
- Node.js 18+
- Claude Code CLI installed: `npm install -g @anthropic-ai/claude-code`
- Login via CLI: `claude login`

## Quick start

```ts
import { claude } from '@instantlyeasy/claude-code-sdk-ts';

const response = await claude()
  .query('Say "Hello World!"')
  .asText();

console.log(response);
```

## Core API surface

Exports from `src/index.ts`:

- `query(prompt, options?)` async generator (classic API)
- `claude()` fluent API builder
- `ResponseParser`, `QueryBuilder`
- Types: `ClaudeCodeOptions`, `Message`, etc.
- Errors: `AbortError`, `isEnhancedError`, `hasResolution`
- Enhanced helpers: retries, telemetry, token streaming, permission manager

## Fluent API

Common chain:

```ts
const result = await claude()
  .withModel('sonnet')
  .allowTools('Read', 'Write')
  .skipPermissions()
  .inDirectory('/path/to/project')
  .query('Refactor this code')
  .asText();
```

Key methods (from docs/FLUENT_API.md):
- `withModel(model)` — `opus` | `sonnet`
- `withTimeout(ms)`
- `debug(true)`
- `allowTools(...tools)` / `denyTools(...tools)` / `allowTools()` (deny all)
- `skipPermissions()` / `acceptEdits()` / `withPermissions('default')`
- `inDirectory(path)` / `addDirectory(path|path[])`
- `withEnv(env)`
- `withMCP({command,args}, ...)`
- `withSignal(signal)`
- `onMessage(handler)` / `onAssistant(handler)` / `onToolUse(handler)`

## Response parsing

```ts
const parser = claude().query('Your prompt');
const text = await parser.asText();
const result = await parser.asResult();
const messages = await parser.asArray();
const data = await parser.asJSON<MyType>();
const tools = await parser.asToolExecutions();
const usage = await parser.getUsage();
```

## Sessions

```ts
const session = claude().withModel('sonnet').skipPermissions();
const response1 = await session.query('Pick a number').asText();
const sessionId = await session.query('').getSessionId();
const response2 = await session.withSessionId(sessionId)
  .query('What number did you pick?')
  .asText();
```

## Tool permissions

```ts
await claude()
  .allowTools('Read', 'Write')
  .query('Analyze this code')
  .asText();
```

## Streaming & cancellation

Streaming returns complete messages (not per-token).

```ts
const parser = claude().withSignal(controller.signal).query('Long task');
await parser.stream(async (message) => {
  if (message.type === 'assistant') {
    console.log(message.content[0].text); // full text block
  }
});
```

Cancellation:

```ts
import { AbortError } from '@instantlyeasy/claude-code-sdk-ts';

try {
  await parser.stream(async () => {});
} catch (err) {
  if (err instanceof AbortError) {
    console.log('Cancelled');
  }
}
```

## Logging

```ts
import { ConsoleLogger, LogLevel } from '@instantlyeasy/claude-code-sdk-ts';

const logger = new ConsoleLogger(LogLevel.DEBUG);
await claude().withLogger(logger).query('Debug this').asText();
```

## Event handlers

```ts
await claude()
  .onMessage(msg => console.log('Message:', msg.type))
  .onAssistant(msg => console.log('Claude:', msg))
  .onToolUse(tool => console.log(`Using ${tool.name}...`))
  .query('Explain this');
```

## Auth & environment

Auth is via Claude CLI (`claude login`). SDK delegates auth to CLI.

Environment config: `withEnv({ ... })` or `inDirectory(path)`.

## Build & test

```bash
npm run build
npm test
npm run typecheck
npm run lint
```
