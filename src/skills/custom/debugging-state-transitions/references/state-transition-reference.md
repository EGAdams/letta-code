# State Transition Debugging Reference (Tennis Scoreboard)

## Known fragile transitions
- Match Win Blink (8) -> Regular Play After Score (5) when Undo is pressed.
- After Match Win (7) -> Regular Play After Score (5) when Undo is pressed.
- Regular Play No Score (3) -> Regular Play After Score (5) first score.
- Sleep -> Wake transitions: NO_SCORE_SLEEP_STATE (4) / REGULAR_PLAY_SLEEP_STATE (9).

## Suggested log points
- `StateMachine::run` before/after `handleInput()`.
- `StateMachine::setState` entry/exit with state + action.
- Match win undo branches: `MatchWinBlinkState` + `AfterMatchWinState`.
- `UndoState` after `undo()` + `loopGame()`.
- `ScoreBoard::update()` and `ScoreBoard::resetBlinkState()`.
- `SetDrawer::drawSetsWithSpacing()` to confirm set area clearing.

## Key signals to include
- `gameState.state`
- `gameState.currentAction`
- p1/p2 points/games/sets
- `serve`, `currentSet`
- tie-break flags
- `clockUpdater` paused/resumed status
- `SetDrawer` font height + start row

## Files to inspect first
- `StateMachine/StateMachine.cpp`
- `MatchWinBlinkState/MatchWinBlinkState.cpp`
- `AfterMatchWinState/AfterMatchWinState.cpp`
- `UndoState/UndoState.cpp`
- `ScoreBoard/ScoreBoard.cpp`
- `SetDrawer/SetDrawer.cpp`
- `SetBlinkController/SetBlinkController.cpp`