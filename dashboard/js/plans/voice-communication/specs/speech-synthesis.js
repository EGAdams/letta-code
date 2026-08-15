import { Status } from "../../interface-spec.js";

export const speechSynthesisSpec = {
  id: "speech-synthesis",
  name: "SpeechSynthesizer",
  group: "Shipped ports",
  tagline:
    "Text → spoken reply. Server-side edge-tts, with a per-agent voice catalog and no-overlap guarantee.",
  status: Status.WORKING,
  statusNote:
    "Works and is well tested, but it is the one place a crude form of generation fencing already exists — worth harvesting when VoiceSession lands.",
  responsibility: [
    "Speak an assistant reply, in the voice assigned to the agent that produced it, without ever overlapping a previous reply.",
    "There are two layers: a Python strategy that renders text to audio bytes via edge-tts and caches the result, and a browser-side synthesizer facade that cleans markdown out of the text, picks the right voice, and plays the audio.",
    "The browser side already enforces something the rest of the system lacks: a newer speak() supersedes an in-flight one. That is generation fencing in miniature, implemented locally because there was no session to ask.",
  ],
  contract: {
    language: "text",
    code: `SpeechSynthesisStrategy(ABC)   voice/synthesis.py   (server)

  synthesize(text, voice) -> audio bytes        cached on disk

SpeechSynthesizer   js/abstract/speech-synthesizer.interface.js   (browser)

  supported            -> bool
  speak(text, agentName=null)   cancels any in-flight speech first
  cancel()
  clean(text)          strips markdown so it is not read aloud
  pickVoice() / refreshVoices()

AgentVoiceCatalog   js/abstract/agent-voice-catalog.interface.js
  voiceFor(agentName) -> voice   per-agent preference + gender heuristics`,
  },
  implementations: [
    {
      name: "EdgeTtsSynthesizer",
      kind: "current",
      file: "voice/synthesis.py",
      note: "Server-side edge-tts with on-disk caching.",
    },
    {
      name: "EdgeTtsSpeechSynthesizer",
      kind: "current",
      file: "js/implementation/edge-tts-speech-synthesizer.js",
      note: "The live browser path: POSTs /api/tts and plays the audio.",
    },
    {
      name: "BrowserSpeechSynthesizer",
      kind: "deprecated",
      file: "js/implementation/browser-speech-synthesizer.js",
      note: "Web Speech fallback. Deliberately never substituted for a failed server call — a robotic voice mid-conversation was worse than silence.",
    },
  ],
  dependencies: {
    usedBy: [
      "InputOptionsRenderer — speaks agent replies",
      "Toyota's receptionist box",
    ],
    dependsOn: [
      "edge-tts (server)",
      "HTMLAudioElement (browser)",
      "POST /api/tts",
    ],
    note: "The browser facade holds no voice policy of its own — AgentVoiceCatalog owns per-agent voice choice, so adding an agent does not touch the synthesizer.",
  },
  developmentStatus: {
    done: [
      "Replies never overlap: speak() cancels in-flight audio, and a newer speak supersedes an older one.",
      "Markdown is stripped before speaking, and text that is only markdown says nothing rather than reading punctuation aloud.",
      "Per-agent voices persist to both localStorage and Letta agent metadata, with the local cache used when metadata is unavailable.",
      "Three separate failure modes are covered by tests and all resolve to silence rather than a robotic fallback: non-audio server reply, rejected fetch, and blocked playback.",
      "Server-side synthesis is cached on disk, so repeated phrases do not re-synthesize.",
    ],
    gaps: [
      "The no-overlap rule is enforced inside the synthesizer rather than by a session, so it only knows about speech, not about which agent turn the speech belonged to.",
      "There is no SpokenOutputPolicy: nothing centrally decides that reasoning, tool calls and status events must never be spoken. Each renderer composes speakable text itself.",
      "No barge-in — speaking does not stop because the user started talking.",
    ],
  },
  tests: {
    files: [
      {
        path: "js/tests/edge-tts-speech-synthesizer.test.js",
        count: 12,
        proves:
          "The server path end to end, voice overrides per agent, that a newer speak supersedes an in-flight one, and that three distinct server/playback failures never fall back to a browser voice.",
      },
      {
        path: "js/tests/speech-synthesizer.test.js",
        count: 9,
        proves:
          "Voice selection preferences, markdown cleaning, cancel-then-speak ordering, and that abstract primitives throw on the base class.",
      },
      {
        path: "js/tests/agent-voice-catalog.test.js",
        count: 7,
        proves:
          "Per-agent voice assignment and the gender-preference heuristics.",
      },
      {
        path: "dashboard/tests/test_synthesis.py",
        count: 4,
        proves:
          "edge-tts invocation and caching, plus that invalid input, a missing binary, a process failure and a timeout are all reported rather than producing empty audio.",
      },
    ],
    untested: [
      "Nothing asserts that reasoning or tool-call text is never passed to speak() — that rule lives in renderer code and is unprotected.",
      "Barge-in, because it does not exist.",
    ],
    next: [
      "A SpokenOutputPolicy with a test proving reasoning/tool/status events are rejected. This is the plan's Chain-of-Responsibility object and the one piece of it worth building before the rest.",
    ],
  },
  diagrams: [
    {
      title: "Speaking one reply",
      caption:
        "The supersede step is local generation fencing. When VoiceSession exists, this logic should move behind it rather than being reimplemented.",
      code: `sequenceDiagram
  participant R as Renderer
  participant SS as EdgeTtsSpeechSynthesizer
  participant Cat as AgentVoiceCatalog
  participant TTS as POST /api/tts
  participant Edge as edge-tts

  R->>SS: speak(reply, "Toyota")
  SS->>SS: cancel in-flight audio
  SS->>Cat: voiceFor("Toyota")
  Cat-->>SS: en-GB-SoniaNeural
  SS->>TTS: {text, voice}
  TTS->>Edge: synthesize (cached on disk)
  Edge-->>TTS: audio bytes
  TTS-->>SS: audio
  SS->>SS: play
  Note over SS: a newer speak() here<br/>supersedes this playback`,
    },
    {
      title: "The missing output gate",
      caption:
        "Today each renderer decides what is speakable. SpokenOutputPolicy would make that one composable chain instead.",
      code: `flowchart LR
  E1[assistant_text]
  E2[reasoning]
  E3[tool_call]
  E4[status]
  SOP{{"SpokenOutputPolicy<br/>PLANNED"}}
  TTS[SpeechSynthesizer]
  E1 --> SOP
  E2 --> SOP
  E3 --> SOP
  E4 --> SOP
  SOP -->|"only speakable text"| TTS
  style SOP stroke-dasharray: 6 4,stroke:#9b2c39,color:#9b2c39`,
    },
  ],
  nextWork: [
    "Build SpokenOutputPolicy as composable gates, with a failing test for 'reasoning is never spoken'.",
    "Move the supersede rule behind VoiceSession once it exists, instead of keeping it inside the synthesizer.",
    "Add barge-in after ContinuousListener can signal speech start.",
  ],
};
