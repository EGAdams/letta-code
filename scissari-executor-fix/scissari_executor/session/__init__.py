"""F7 — the transport/session layer.

F1-F6 live INSIDE executor_run. F7 is lettabot's session lifecycle around the
letta-code SDK subprocess: the coarse 300_000ms stream-inactivity timer kills
healthy-but-slow tool calls, and the next heartbeat writes to a dead subprocess
(pid=undefined) instead of re-spawning it.

This package divides that into three testable objects:
  - SessionHealth      (State machine)  — per-tool-call deadline != stream-idle
  - ToolCallKeepalive  (Observer)       — suppress idle timer during a tool call
  - ResilientTransport (Proxy/Decorator)— re-spawn a dead subprocess on send()
and a SessionSupervisor (Facade) the bot + heartbeat call instead of the raw SDK.
"""
