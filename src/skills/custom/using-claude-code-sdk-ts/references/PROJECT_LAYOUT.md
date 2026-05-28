# Project layout (claude-code-sdk-ts)

Root: `/home/adamsl/claude-code-sdk-ts`

## Key paths
- `README.md` — primary usage guide and examples
- `docs/FLUENT_API.md` — fluent API details
- `docs/CLASSIC_API.md` — async generator API
- `docs/ERROR_HANDLING.md` — error types and retry behavior
- `docs/ENVIRONMENT_VARIABLES.md` — env vars
- `docs/ENHANCED_FEATURES.md` — token streaming, telemetry, permissions
- `src/index.ts` — public exports
- `src/fluent.ts` — fluent API implementation
- `src/parser.ts` — response parsing
- `src/errors.ts` — error classes
- `src/types.ts` — core types
- `src/enhanced/` — retry, telemetry, token streaming utilities
- `examples/` — runnable samples

## Build/test scripts
From `package.json`:
- `npm run build`
- `npm test`
- `npm run typecheck`
- `npm run lint`
- `npm run format`
