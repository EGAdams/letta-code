---
name: running-tennis-scoreboard
description: Document and guide build/run/debug workflows for the tennis scoreboard controller, especially `run_remote_listener` and its state machine. Use when implementing scoreboard behavior, diagnosing remote or keyboard input issues, tuning timing delays, or tracing transitions across gameplay, pairing, sleep, undo, and match-win states.
---

# Running Tennis Scoreboard

## Overview

Use this skill to compile, run, and debug the tennis scoreboard controller process with repeatable steps.
Prioritize `run_remote_listener`, `RemoteListenerContext`, and state transitions before changing rendering or hardware glue code.

## Quick Start: Build and Run

1. Build the controller:
   - `make run_remote_listener`
2. Inspect supported flags before testing:
   - `./run_remote_listener --help`
3. Run with the actual supported flags:
   - Testing mode: `./run_remote_listener --testing` or `./run_remote_listener -t`
   - Loop harness: `./run_remote_listener --loop`
   - Test file input: `./run_remote_listener --test-file path/to/test_input.txt` or `./run_remote_listener -f path/to/test_input.txt`
   - Keyboard input: `./run_remote_listener --keyboard` or `./run_remote_listener -k`
   - Test-to-keyboard bridge: `./run_remote_listener --test-to-keyboard` or `./run_remote_listener --ttk`
   - Digi/remote hardware path: `./run_remote_listener --digi`
4. If flags differ in your branch, read argument parsing in `run_remote_listener.cpp` and adapt commands exactly to that parser.

## Runtime Configuration Files

Tune runtime timing through plain-text millisecond files read at startup:

- `game_blink_slowdown_delay_ms.txt`: Slow-motion blink pacing during game-point/match-point style flashes.
- `set_win_flash_delay_ms.txt`: Flash cadence for set-win feedback.
- `main_game_delay.txt`: Baseline frame/update delay for regular gameplay loop timing.

Resolve file locations with home-directory rules:

- If `SUDO_USER` is set, treat `/home/$SUDO_USER` as the effective home for config lookup.
- Otherwise use `HOME`.
- Place timing files in that effective home (or the exact path expected by your branch).
- Re-read values by restarting the process unless hot-reload is explicitly implemented.

## Input Modes

Use modes to isolate bugs and verify state behavior:

- Remote mode (default, no flag): consume live remote/controller events for pairing and real-device validation.
- Keyboard mode: `--keyboard` / `-k` for local development without hardware.
- Testing mode: `--testing` / `-t`, optionally with `--test-file path/to/test_input.txt` (or `-f ...`) for deterministic replay.
- Test-to-keyboard mode: `--test-to-keyboard` / `--ttk` to bridge test streams into keyboard-style events.
- Loop mode: `--loop` to repeat runs for soak and timing stability checks.
- Digi mode: `--digi` to use the DigiScoreBoard hardware path.

## State Machine Map

State handling is driven by `GameState` and state handlers. Use this map as a state inventory and debugging guide:

- `PairingModeState`
- `SleepModeState`
- `RegularGamePlayBeforeScoreState`
- `RegularGamePlayAfterScoreState`
- `MatchWinBlinkState`
- `AfterMatchWinState`
- `UndoState`
- `IntroductionScreenState`

Do not assume fixed transition paths across all branches. In practice, transitions are typically triggered by events such as pairing completion, inactivity timeout, match-win detection, undo actions, and sleep wake events.

Keep `StateMachine` transition rules centralized. Route side effects through `RemoteListenerContext` so rendering, timers, and input adapters remain consistent.

## Debugging and Troubleshooting Checklist

Run this checklist before broad refactors:

1. Pairing stuck:
   - Verify `PairingModeState` receives input callbacks.
   - Confirm remote mode is active and expected device IDs are visible.
   - Reset to `IntroductionScreenState` and pair again.
2. Sleep/wake issues:
   - Confirm inactivity timers and wake events in `SleepModeState`.
   - Check whether wake returns to intro/pairing or gameplay as intended.
3. Blink timing wrong:
   - Validate values in `game_blink_slowdown_delay_ms.txt` and `set_win_flash_delay_ms.txt`.
   - Restart process and re-measure timing in logs.
4. Match win hold too short/long:
   - Inspect `MatchWinBlinkState` exit condition and `AfterMatchWinState` hold behavior.
   - Verify `main_game_delay.txt` does not mask expected hold duration.
5. Undo behaves inconsistently:
   - Confirm `UndoState` restores score/game/set context atomically.
   - Confirm transition target is correct pre-score vs post-score state.

## Core Files to Inspect First

- `run_remote_listener.cpp`
- `RemoteListenerContext`
- `StateMachine`
- `PairingModeState`
- `SleepModeState`
- `RegularGamePlayBeforeScoreState`
- `RegularGamePlayAfterScoreState`
- `MatchWinBlinkState`
- `AfterMatchWinState`
- `UndoState`
- `IntroductionScreenState`
- `TennisConstants`

Use `TennisConstants` for score semantics and thresholds before hard-coding values in states.
