import { Status } from "../../interface-spec.js";

export const detectionInterfaceSpec = {
  id: "detection-interface",
  name: "DetectionInterface",
  group: "Superseded prototype",
  tagline:
    "The prototype's turn-detection seam. Replaced by three narrower shipped seams, not one.",
  status: Status.SUPERSEDED,
  statusNote:
    "Real code, real implementations, but only in /home/adamsl/voice_agent — nothing in the dashboard uses it.",
  responsibility: [
    "In the prototype: decide when to start recording and when to stop, given raw audio blocks and a frame count. Two implementations answered it — press a key, or wait for silence.",
    "It was the prototype's best seam. The plan's audit called it 'a good early Strategy seam' while noting it conflated three jobs: start policy, stop policy, and terminal presentation — and forced KeyboardDetection to accept audio arguments it never used, which is an Interface Segregation failure.",
    "The interesting finding for this workspace is what replaced it. 'Detection' did not become one interface in the shipped system; it became three, each with a different reason to change: when speech arrives (ContinuousListener), who is being addressed (RouteStrategy), and whether the instruction is finished (CommandCompletenessStrategy).",
  ],
  contract: {
    language: "python",
    code: `DetectionInterface(ABC)   voice_agent/audio_capture/detection_interface.py

  should_start_recording()                    -> bool
  should_stop_recording(audio_block, frames)  -> bool
  reset()                                     -> None

Note the segregation problem: KeyboardDetection must accept
audio_block and frame_count, and ignores both.`,
  },
  implementations: [
    {
      name: "KeyboardDetection",
      kind: "deprecated",
      file: "voice_agent/audio_capture/keyboard_detection.py",
      note: "Press-to-talk. Ignores the audio arguments it is forced to accept.",
    },
    {
      name: "SilenceDetection",
      kind: "deprecated",
      file: "voice_agent/audio_capture/silence_detection.py",
      note: "Amplitude-threshold stop policy — the fixed-timeout approach the note-command channel deliberately rejects.",
    },
    {
      name: "ContinuousListener",
      kind: "current",
      file: "js/abstract/continuous-listener.interface.js",
      note: "Successor for 'when does speech arrive' — see the Audio Capture tab.",
    },
    {
      name: "CommandCompletenessStrategy",
      kind: "current",
      file: "voice/note_ports.py",
      note: "Successor for 'is the user finished' — judged from text, not silence.",
    },
    {
      name: "RouteStrategy",
      kind: "current",
      file: "router/classify.py",
      note: "Successor for 'who is being addressed'.",
    },
  ],
  dependencies: {
    usedBy: ["AudioCapture (prototype only)"],
    dependsOn: ["numpy", "sounddevice", "terminal output"],
    note: "The prototype's detection code depended directly on numpy arrays and printed to the terminal, which is why it cannot be reused in a browser context.",
  },
  developmentStatus: {
    done: [
      "Two working implementations exist in the prototype and prove the Strategy shape was right.",
      "Its lesson is captured in the shipped design: turn-end is a policy, not a timer.",
    ],
    gaps: [
      "Not used by anything that runs today.",
      "Cannot be ported as-is: it is built on numpy audio blocks, while the shipped browser path never sees raw audio.",
      "The plan's intended replacement (Pipecat VAD + a Smart Turn strategy) has not been started.",
    ],
  },
  tests: {
    files: [
      {
        path: "voice_agent/test_voice_capture.py, test_recording_process*.py",
        proves:
          "Prototype-level capture behaviour including a mock audio generator. Useful as fixtures; not run by the dashboard suite.",
      },
    ],
    untested: [
      "Nothing in the dashboard test suite covers this file — it is outside the repo.",
    ],
    next: [
      "No new tests. If the Pipecat rebuild starts, convert the prototype's recordings into characterization fixtures as Phase 0 requires.",
    ],
  },
  diagrams: [
    {
      title: "One interface became three",
      caption:
        "Each successor has a different reason to change, which is why they did not merge back into a single detection port.",
      code: `flowchart LR
  DI["DetectionInterface<br/>(prototype)"]
  DI -->|"when does speech arrive?"| CL["ContinuousListener<br/>State, shipped"]
  DI -->|"is the instruction finished?"| CC["CommandCompletenessStrategy<br/>LLM-judged, shipped"]
  DI -->|"who is being addressed?"| RS["RouteStrategy<br/>2-tier, shipped"]
  style DI stroke-dasharray: 5 4`,
    },
  ],
  nextWork: [
    "Leave it alone. It is history, and the plan explicitly says not to port it.",
    "If the Pipecat slice ever starts, harvest its WSL device-discovery notes and recordings as fixtures rather than code.",
  ],
};
