# Voice Session

`src/` owns the typed conversation lifecycle and its clock/id ports. The
dashboard still loads JavaScript without a bundler, so `dist/` contains the
checked-in ES modules compiled from TypeScript. Existing JavaScript imports use
the small compatibility entries `../voice-session.js` and `../session-clock.js`.

After changing a `.ts` file, compile before testing or committing:

```bash
./node_modules/.bin/tsc -p dashboard/js/abstract/voice_session/tsconfig.json
bunx --bun @biomejs/biome@2.2.5 check --write dashboard/js/abstract/voice_session/dist
bun test dashboard/js/tests/voice-session.test.js dashboard/js/tests/system-session-primitives.test.js dashboard/js/tests/spoken-output-policy.test.js
```

`tsconfig.json` lives at this module root because it controls this module's
`src/` and `dist/` directories; the repo root config builds the separate CLI.
The session owns state and generation fencing. `SpokenOutputPolicy` remains a
separate Strategy that consumes the session's `accepts()` method.
