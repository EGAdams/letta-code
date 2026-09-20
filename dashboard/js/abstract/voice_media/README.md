# Voice Media

This module will hold the provider neutral TypeScript voice media contract used
by the dashboard browser. It sits beside `voice_session/` in `js/abstract/`.
Concrete browser behavior remains in `js/implementation/voice_media/`.

`src/` is reserved for typed interfaces, `tests/` for their contract tests,
and `diagrams/` for class, flow, and sequence diagrams. The module-local
`tsconfig.json` will compile `src/` to checked-in `dist/` when TypeScript
source is added. The Pipecat adapter itself belongs on the Python side of the
media port in `dashboard/voice/media/ports.py`.
