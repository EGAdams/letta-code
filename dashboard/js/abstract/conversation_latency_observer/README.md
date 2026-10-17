# Conversation Latency Observer

`ConversationLatencyObserver` is the typed Observer for one conversation
turn's timing milestones. Producers report milestones without depending on a
logger, UI, or storage mechanism. The observer keeps independent traces,
records the first occurrence of each milestone, derives actionable durations,
and publishes an immutable report through `LatencyReportSinkPort`.

The module does not control capture, agent generation, synthesis, playback, or
session state. Those objects remain responsible for behavior and only call the
observer at their existing boundaries.

Wired into `InputOptionsRenderer`
(`dashboard/js/implementation/detail-renderers.js`), the one consumer today —
see [`conversation_coordinator`'s README](../conversation_coordinator/README.md)
for the actual mark sites. Reports currently publish through
`ConsoleLatencySink` (`dashboard/js/implementation/latency-telemetry.js`,
`console.debug`); swapping in a durable sink (e.g. an HTTP endpoint appending
to a JSON log, like `voice_transcripts.json`) is a follow-up, not required by
this port.

Run its focused tests with:

```bash
bun test dashboard/js/abstract/conversation_latency_observer/tests
```

