# Latency trace flow

Every conversation turn receives an independent trace. A milestone is recorded
only for a live trace and only once, so retries and repeated stream chunks do
not change the first occurrence measurements. Finishing, interruption, and
failure all close the trace and publish a report.

```mermaid
flowchart TD
  A[Begin conversation trace] --> B[Capture context and start time]
  B --> C[Receive typed milestone]
  C --> D{Trace is active?}
  D -->|no| E[Reject stale milestone]
  D -->|yes| F{Milestone already recorded?}
  F -->|yes| G[Keep original first occurrence]
  F -->|no| H[Read monotonic clock]
  H --> I[Store milestone sample]
  I --> J{Trace ending?}
  G --> J
  J -->|no| C
  J -->|yes| K[Derive stage durations]
  K --> L[Build immutable latency report]
  L --> M[Publish through report sink]
  M --> N[Remove active trace]
```

The first report should expose these actionable intervals:

- speech ended to transcript ready;
- agent request to first assistant delta;
- first assistant delta to first complete sentence;
- first TTS request to audio ready;
- audio ready to playback start; and
- speech ended or agent request to first audible reply.

