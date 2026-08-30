# Toyota Input Options — Agent Blocks Working Map

Last verified: 2026-08-29

## Working directories

New development belongs here:

- Source objects: `/home/adamsl/agent_blocks/voice_communication`
- Mirrored documentation SPA: `/home/adamsl/agent_blocks/spa_documentation/voice_communication`

The existing implementation under `/home/adamsl/letta-code/dashboard` is the
behavioral reference and migration source. Do not mistake it for the new Agent
Blocks source tree, and do not duplicate an existing dashboard object without
first deciding whether to migrate, adapt, or replace it.

Before changing Agent Blocks, read:

- `/home/adamsl/agent_blocks/AGENTS.md`
- `/home/adamsl/agent_blocks/CLAUDE.md`
- `/home/adamsl/agent_blocks/voice_communication/README.md`
- `/home/adamsl/agent_blocks/spa_documentation/CLAUDE.md` before SPA work
- `/home/adamsl/agent_blocks/spa_documentation/skills/building-the-spa/SKILL.md`
  before SPA work

## Current status

`agent_blocks/voice_communication` is a typed source skeleton. It defines the
target TypeScript interfaces, Pydantic boundary models, and Python Protocols,
but it is not yet Toyota's live runtime.

Toyota's working interface remains in `letta-code/dashboard`. Some of the
intended blocks are already implemented and tested there, but Toyota's renderer
does not yet compose them all. The first planned adoption is
`IConversationAgent` plus `LettaAgentAdapter`.

Important current differences:

- `InputOptionsRenderer.send()` still performs its own
  `POST /api/letta-code-message` request.
- A tested `LettaAgentAdapter` already exists in the dashboard tree, but the
  renderer does not receive it through dependency injection yet.
- A tested `VoiceSession` exists in the dashboard tree, but Toyota does not own
  one yet.
- `IToyotaVoiceApplication` in Agent Blocks is only a facade interface.
- Pipecat remains a planned separate local service. It must not be embedded in
  the dashboard process.
- The old Toyota note-command channel remains in the dashboard tree as unused,
  tested reference code. Toyota's current home-screen interface uses one
  editable dark text surface.
- Terminal helpers and the terminal backend still exist, but the current
  `InputOptionsRenderer` sets its terminal to `null`; old terminal notes and
  comments can therefore be stale.

## Construction Status task navigation

`IConversationAgent` is the first working example of using an Agent Block's
Construction Status page as the task plan:

- Plan source of truth:
  `/home/adamsl/agent_blocks/spa_documentation/voice_communication/conversation_agent/basic_agent_construction_status.html`
- Generic drill-down behavior:
  `/home/adamsl/agent_blocks/spa_documentation/app.js`
- Shared task-tree styling:
  `/home/adamsl/agent_blocks/spa_documentation/styles.css`
- Reusable authoring convention:
  `/home/adamsl/agent_blocks/spa_documentation/skills/building-the-spa/SKILL.md`

When Construction Status contains a `.construction-task-tree`, that tree stays
hidden as the source definition. The sidebar shows one task level at a time,
and the main pane shows only the selected task's details. Parent task tabs
receive the existing red Excel comment/note corner triangle; leaf task tabs do
not. Clicking a parent fans out its direct children. Back collapses one task
level and eventually returns to the five object detail tabs. Construction
Status pages without this markup keep their prior behavior.

The old IConversationAgent Construction Status placeholder was intentionally
discarded. Its replacement skeleton tracks contract reconciliation, Toyota
adoption, and one verified Pipecat voice slice. Input clearing was removed from
that interface's ownership: the Input Draft and Conversation Coordinator now
carry the clearing work, while VoiceSession carries stale-generation fencing.
These are plans, not completion evidence.

Taskmaster is not a runtime dependency of this design. This repository has a
`task-master-ai` entry in `/home/adamsl/letta-code/.mcp.json`, but on the last
verification its MCP tools were not exposed to the active Codex session and
the configured `task-master-ai` executable was not on `PATH`. The HTML task
tree is sufficient for manual planning. Revisit Taskmaster only if we need MCP
task mutation, dependency scheduling, automatic next-task selection, or
multi-agent task claiming; keep the Construction Status document as the
human-visible projection even then.

## New Agent Blocks source

Root and public catalogs:

- `/home/adamsl/agent_blocks/voice_communication/README.md`
- `/home/adamsl/agent_blocks/voice_communication/index.ts`
- `/home/adamsl/agent_blocks/voice_communication/interfaces/index.ts`
- `/home/adamsl/agent_blocks/voice_communication/interfaces/__init__.py`
- `/home/adamsl/agent_blocks/voice_communication/typescript_contracts/contracts.ts`
- `/home/adamsl/agent_blocks/voice_communication/pydantic_models/models.py`

Toyota/application-side blocks:

- `input_draft/input_draft.ts`
- `conversation_agent/conversation_agent.ts`
- `letta_agent_adapter/letta_agent_adapter.ts`
- `voice_session/voice_session.ts`
- `spoken_output_policy/spoken_output_policy.ts`
- `conversation_coordinator/conversation_coordinator.ts`
- `route_strategy/route_strategy.ts`
- `language_processor/language_processor.ts`
- `note_command_channel/note_command_channel.ts`
- `pipecat_service_client/pipecat_service_client.ts`
- `toyota_voice_application/toyota_voice_application.ts`
- `voice_health_observer/voice_health_observer.ts`

Python/service-side blocks:

- `audio_capture/audio_capture.py`
- `detection_interface/detection_interface.py`
- `transcription_strategy/transcription_strategy.py`
- `speech_synthesizer/speech_synthesizer.py`
- `pipeline_factory/pipeline_factory.py`
- `pipecat_local_service/pipecat_local_service.py`

Planned construction order:

1. Adopt `IConversationAgent` and `LettaAgentAdapter` in Toyota.
2. Build `InputDraft` reset semantics and give Toyota a `VoiceSession` with
   capture-generation fencing.
3. Compose `ConversationCoordinator` around clear, listen, transcript, and
   send ordering.
4. Adopt `SpokenOutputPolicy` and interruption rules.
5. Build the typed Pipecat client/service boundary and pipeline factory.
6. Compose `ToyotaVoiceApplication`.
7. Add `VoiceHealthObserver` and controlled rollout.

## Existing Toyota/Input Options implementation

### Browser composition and UI

- Home-screen container: `/home/adamsl/letta-code/dashboard/dashboard.html`
  (`#receptionist-box` under the Toyota section)
- Toyota composition root:
  `/home/adamsl/letta-code/dashboard/js/boot/receptionist.js`
- Generic per-agent Input Options composition:
  `/home/adamsl/letta-code/dashboard/js/boot/agent-detail-renderers.js`
- Main renderer and send/model/voice/recording behavior:
  `/home/adamsl/letta-code/dashboard/js/implementation/detail-renderers.js`
  (`InputOptionsRenderer`)
- Toyota's editable dark surface:
  `/home/adamsl/letta-code/dashboard/js/implementation/textarea-note-surfaces.js`
  (`EditableDarkNoteSurface`)
- Dashboard composition root:
  `/home/adamsl/letta-code/dashboard/js/dashboard-boot.js`
- Styles: `/home/adamsl/letta-code/dashboard/css/dashboard.css`

Toyota's current browser flow is:

```text
dashboard.html #receptionist-box
  -> startReceptionist()
  -> resolve /api/receptionist-agent
  -> construct InputOptionsRenderer for Toyota
  -> inject EditableDarkNoteSurface + BrowserSpeechRecognitionListener
  -> send text through /api/letta-code-message
```

### Existing browser objects relevant to Agent Block adoption

- Conversation port:
  `dashboard/js/abstract/conversation-agent.interface.js`
- Letta adapter:
  `dashboard/js/implementation/letta-agent-adapter.js`
- Session lifecycle:
  `dashboard/js/abstract/voice-session.js`
- Spoken-output policy:
  `dashboard/js/abstract/spoken-output-policy.js`
- One-shot recorder:
  `dashboard/js/implementation/media-recorder-voice-recorder.js`
- Continuous recognition:
  `dashboard/js/implementation/browser-speech-recognition-listener.js`
- Speech output:
  `dashboard/js/implementation/edge-tts-speech-synthesizer.js`
- Transcript state:
  `dashboard/js/abstract/receptionist-transcript-controller.js`
- Transcript/note synchronization:
  `dashboard/js/implementation/transcript-synced-note.js`
- Text surfaces:
  `dashboard/js/implementation/textarea-note-surfaces.js`

### Backend and endpoints

- GET routes: `dashboard/http_app/get_routes.py`
- POST routes: `dashboard/http_app/post_routes.py`
- Terminal WebSocket: `dashboard/http_app/terminal_ws.py`
- Service composition and remaining implementations: `dashboard/server.py`
- Voice pipeline: `dashboard/voice/`
- Agent-name routing: `dashboard/router/`

Input Options depends on these main endpoints:

- `GET /api/receptionist-agent`
- `POST /api/receptionist-intent`
- `POST /api/letta-code-message`
- `POST /api/voice`
- `GET/POST /api/agent-model`
- `GET/POST /api/agent-voice`
- `POST /api/tts`
- `POST /api/note-save`
- `GET /api/terminal` for the retained terminal implementation

The microphone pipeline is:

```text
MediaRecorder
  -> POST /api/voice
  -> dashboard/voice/transcription.py (whisper.cpp)
  -> dashboard/voice/cleanup.py (cleanup agent)
  -> cleaned text returned to InputOptionsRenderer
```

`whisper.cpp` under `/home/adamsl/whisper.cpp` is a live runtime dependency;
do not archive or remove it while this path remains in use.

## Toyota stale-input cause and owning blocks

The visible symptom is not owned by `IConversationAgent`. The current Toyota
continuous-listening path stores text in two places:

- the visible `EditableDarkNoteSurface` textarea;
- the committed/interim state inside `TranscriptBuffer`.

`TranscriptSyncedNote.setText( "" )` can already clear and resynchronize both.
The defect is that the `Start Listening` handler calls `listener.start()`
without first beginning a fresh application capture and clearing through that
synchronized boundary. The next recognition result therefore merges with the
old committed prefix. In addition, the policy-triggered send path explicitly
uses `preserveInput: true`, and the current Toyota renderer test asserts that
the transcript remains after an addressed automatic send.

The first repair slice is divided among these Agent Blocks:

1. `IConversationAgent` — accepts an immutable text snapshot and emits
   normalized events; never clears UI state.
2. `LettaAgentAdapter` — preserves timeout, conversation resume, normalized
   reply, and delivery-side cancellation behavior.
3. `InputDraft` — the new synchronized text-mutation port; one `clear()` empties
   the visible surface and transcript accumulator together.
4. `VoiceSession` — issues capture/turn generations and rejects callbacks from
   superseded listening attempts.
5. `ConversationCoordinator` — owns the ordering transaction: snapshot old
   draft, begin generation, clear, start capture, restore on start failure, and
   accept only current transcript events. It also snapshots and clears accepted
   Send text before submitting through `IConversationAgent`.
6. `ToyotaVoiceApplication` — the composition Facade that injects these blocks
   and binds Toyota's Send and Start Listening controls to the coordinator.

Pipecat is intentionally not required to prove this first clearing slice. The
existing browser listener should be the first capture adapter used for
verification. Once the boundary is green, `PipecatServiceClient` can replace
that adapter at the composition root without changing draft or coordinator
policy.

## Tests that protect the current behavior

Frontend:

- `dashboard/js/tests/detail-renderers.test.js`
- `dashboard/js/tests/receptionist-renderer.test.js`
- `dashboard/js/tests/input-options-note-surface.test.js`
- `dashboard/js/tests/letta-agent-adapter.test.js`
- `dashboard/js/tests/voice-session.test.js`
- `dashboard/js/tests/spoken-output-policy.test.js`
- `dashboard/js/tests/media-recorder-voice-recorder.test.js`
- `dashboard/js/tests/browser-speech-recognition-listener.test.js`
- `dashboard/js/tests/textarea-note-surfaces.test.js`

Backend:

- `dashboard/tests/test_http_app_routes.py`
- `dashboard/tests/test_http_app_route_inventory.py`
- `dashboard/tests/test_http_app_terminal_ws.py`
- `dashboard/tests/test_pipeline.py`
- `dashboard/tests/test_receptionist.py`
- `dashboard/tests/test_agents_registry.py`

Useful checks:

```bash
cd /home/adamsl/letta-code/dashboard
bun test js/tests
.venv/bin/python -m pytest tests/

/home/adamsl/letta-code/node_modules/.bin/tsc \
  -p /home/adamsl/agent_blocks/voice_communication/tsconfig.json
/home/adamsl/agent_blocks/lancedb_memory/.venv/bin/python -m compileall \
  /home/adamsl/agent_blocks/voice_communication
```

## Documentation mirrors

- Agent Blocks SPA overview:
  `/home/adamsl/agent_blocks/spa_documentation/voice_communication/_overview.html`
- SPA navigation catalog:
  `/home/adamsl/agent_blocks/spa_documentation/app.js`
- SPA source mapping:
  `/home/adamsl/agent_blocks/spa_documentation/doc_source_map.py`
- Original dashboard design workspace:
  `/home/adamsl/letta-code/dashboard/voice_communication_plan.html`
- Original dashboard plan objects:
  `/home/adamsl/letta-code/dashboard/js/plans/voice-communication/`
- Current runtime documentation:
  `/home/adamsl/letta-code/dashboard/docs/voice.md`

The SPA is a progress tracker. Imported diagrams are design references, not
evidence that a new Agent Block is implemented or adopted by Toyota.

## IConversationAgent university-textbook overview

The IConversationAgent object overview now uses the same university-textbook
visual language as the LanceDB Memory `Turn` object:

- `/home/adamsl/agent_blocks/spa_documentation/voice_communication/conversation_agent/basic_agent.html`
- Chapter title: **The IConversationAgent — A Stable Doorway to Any Agent Backend**
- The explanation centers on the deliberately narrow `submit( text,
  generation ) -> AsyncIterable<AgentEvent>` boundary.
- It distinguishes the interface from Toyota UI, Letta adapters, Pipecat,
  speech recognition, spoken-output policy, and text-to-speech.
- It explains why Toyota must both clear the draft at capture start and reject
  late events whose generation no longer matches the active generation.
- The page accurately labels the block as a design skeleton; the typed contract
  exists, but Toyota adoption and the Pipecat vertical slice remain incomplete.

Construction Status remains a separate task-oriented page at
`basic_agent_construction_status.html`. Its hidden task tree is the navigation
source of truth. Its university-textbook landing chapter calculates total,
current, planned, done, and completion values from that tree. Selecting a task
replaces the landing chapter with a dynamically generated textbook lesson that
explains the task purpose, status, scoped counts, and whether to drill into
children or collect leaf-task evidence. The full hierarchy is never rendered
in the content pane.

The same dynamic textbook Construction Status is now active for the complete
first clearing slice:

- `conversation_agent` — 18 tasks;
- `letta_agent_adapter` — 16 tasks;
- `input_draft` — 10 tasks;
- `voice_session` — 14 tasks;
- `conversation_coordinator` — 18 tasks;
- `toyota_voice_application` — 17 tasks.

Only `InputDraft` is marked current so construction can proceed one block at a
time; the other five object plans remain planned dependencies. Every top-level
workstream is red-tagged because it fans out. Leaves are deliberately
small, independently verifiable outcomes; split them again whenever one leaf
contains multiple responsibilities or unrelated proof. The generic renderer
uses each page's `data-construction-object` value so focused textbook lessons
name their real owner instead of always saying IConversationAgent.

Last browser verification on 2026-08-29 confirmed all six landing chapters,
live totals, one-level-at-a-time navigation, red branch triangles, leaf lessons,
hidden source trees, and shared textbook masthead sizing. The Voice
Communication overview rendered five Mermaid SVGs; zoom and reset were also
exercised after adding InputDraft to the target architecture.
