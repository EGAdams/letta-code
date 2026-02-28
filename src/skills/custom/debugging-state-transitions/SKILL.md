---
name: debugging-state-transitions
description: Documents a repeatable workflow for diagnosing tennis scoreboard state-machine transitions, especially match win, sleep/wake, undo, and display update glitches. Use when debugging state transitions, clipped set numbers, or missing redraws in run_remote_listener.
---

# Debugging State Transitions

## Overview
Use this skill to diagnose recurring state-machine glitches in the tennis scoreboard (match win, undo, sleep/wake). It provides a repeatable workflow, key log points, and reference notes.

## Workflow
1. **Enable tracing**
   - Use the compile-time flag `ENABLE_STATE_TRANSITION_TRACING` (default on in `StateTransitionTracer.h`).
   - Rebuild `run_remote_listener` after changes.

2. **Reproduce with deterministic input**
   - Prefer `--test-file` or `--keyboard` to minimize noise.
   - Capture logs around the transition window (e.g., match win → undo → regular play).

3. **Inspect tracer output**
   - Focus on `StateMachine::setState` and `StateMachine::run` before/after `handleInput()`.
   - Confirm `gameState.state`, `currentAction`, and set/point values match expectations.

4. **Verify redraw triggers**
   - Ensure `ScoreBoard::resetBlinkState()` + `update()` are invoked on undo and wake paths.
   - Validate `SetDrawer::drawSetsWithSpacing()` logs to confirm the set area clear height matches the font height.

## Common Transition Hotspots
- Match Win Blink (8) → Regular Play After Score (5) on UNDO.
- After Match Win (7) → Regular Play After Score (5) on UNDO.
- Regular Play No Score (3) → Regular Play After Score (5) on first score.
- Sleep → Wake transitions (states 4 and 9).

## References
- See `references/state-transition-reference.md` for a checklist of fragile transitions and log points.
